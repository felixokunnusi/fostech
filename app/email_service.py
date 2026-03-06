import smtplib
import threading
import time
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional, Tuple, List

from flask import current_app


class EmailSendError(Exception):
    pass


@dataclass
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = True


# provider -> unix timestamp until when it should be skipped
_PROVIDER_COOLDOWNS: dict[str, float] = {}
_PROVIDER_LOCK = threading.Lock()


def _require(val: Optional[str], name: str) -> str:
    if not val:
        raise RuntimeError(f"{name} is missing. Set it in .env / Render env vars.")
    return val


def _get_sender() -> str:
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME")
    return _require(sender, "MAIL_DEFAULT_SENDER (or MAIL_USERNAME)")


def _provider_chain() -> List[str]:
    chain = current_app.config.get("EMAIL_PROVIDER_CHAIN") or ""
    if chain.strip():
        return [p.strip().lower() for p in chain.split(",") if p.strip()]
    return [(current_app.config.get("EMAIL_PROVIDER") or "brevo").strip().lower()]


def _load_smtp(provider: str) -> SmtpConfig:
    p = provider.lower()

    if p == "brevo":
        return SmtpConfig(
            host=current_app.config.get("BREVO_SMTP_HOST", "smtp-relay.brevo.com"),
            port=int(current_app.config.get("BREVO_SMTP_PORT", 587)),
            username=_require(current_app.config.get("BREVO_SMTP_USERNAME"), "BREVO_SMTP_USERNAME"),
            password=_require(current_app.config.get("BREVO_SMTP_PASSWORD"), "BREVO_SMTP_PASSWORD"),
            use_tls=True,
        )

    if p == "mailgun":
        return SmtpConfig(
            host=current_app.config.get("MAILGUN_SMTP_HOST", "smtp.mailgun.org"),
            port=int(current_app.config.get("MAILGUN_SMTP_PORT", 587)),
            username=_require(current_app.config.get("MAILGUN_SMTP_USERNAME"), "MAILGUN_SMTP_USERNAME"),
            password=_require(current_app.config.get("MAILGUN_SMTP_PASSWORD"), "MAILGUN_SMTP_PASSWORD"),
            use_tls=True,
        )

    if p == "mailersend":
        return SmtpConfig(
            host=current_app.config.get("MAILERSEND_SMTP_HOST", "smtp.mailersend.net"),
            port=int(current_app.config.get("MAILERSEND_SMTP_PORT", 587)),
            username=_require(current_app.config.get("MAILERSEND_SMTP_USERNAME"), "MAILERSEND_SMTP_USERNAME"),
            password=_require(current_app.config.get("MAILERSEND_SMTP_PASSWORD"), "MAILERSEND_SMTP_PASSWORD"),
            use_tls=True,
        )

    if p == "zoho":
        return SmtpConfig(
            host=current_app.config.get("ZOHO_SMTP_HOST", "smtp.zoho.com"),
            port=int(current_app.config.get("ZOHO_SMTP_PORT", 587)),
            username=_require(current_app.config.get("ZOHO_SMTP_USERNAME"), "ZOHO_SMTP_USERNAME"),
            password=_require(current_app.config.get("ZOHO_SMTP_PASSWORD"), "ZOHO_SMTP_PASSWORD"),
            use_tls=True,
        )

    raise RuntimeError(f"Unknown EMAIL provider: {provider}")


def _smtp_send(cfg: SmtpConfig, msg: EmailMessage) -> None:
    with smtplib.SMTP(cfg.host, cfg.port, timeout=20) as server:
        server.ehlo()
        if cfg.use_tls:
            server.starttls()
            server.ehlo()
        server.login(cfg.username, cfg.password)
        server.send_message(msg)


def _is_on_cooldown(provider: str) -> bool:
    now = time.time()
    with _PROVIDER_LOCK:
        until = _PROVIDER_COOLDOWNS.get(provider, 0)
        if until <= now:
            _PROVIDER_COOLDOWNS.pop(provider, None)
            return False
        return True


def _mark_provider_failed(provider: str, seconds: int, reason: str) -> None:
    until = time.time() + seconds
    with _PROVIDER_LOCK:
        _PROVIDER_COOLDOWNS[provider] = until
    current_app.logger.warning(
        "Email provider put on cooldown: provider=%s cooldown_seconds=%s reason=%s",
        provider, seconds, reason
    )


def _clear_provider_cooldown(provider: str) -> None:
    with _PROVIDER_LOCK:
        _PROVIDER_COOLDOWNS.pop(provider, None)


def _cooldown_seconds_for_error(err: Exception) -> int:
    msg = str(err).lower()

    # auth/config problems: retry later but not constantly
    if any(x in msg for x in ["authentication", "auth", "username", "password", "login failed"]):
        return 1800  # 30 min

    # provider/rate/network issues: shorter cooldown
    if any(x in msg for x in ["rate", "quota", "too many", "temporar", "timeout", "connection", "421", "450", "451", "452"]):
        return 300  # 5 min

    # default
    return 600  # 10 min


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """
    Sends via provider chain with cooldown-aware failover.
    Returns: (provider_used, previous_error_if_any)
    """
    sender = _get_sender()

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject

    if not text_content:
        text_content = "Please open this email in an HTML-capable email client."
    msg.set_content(text_content)
    msg.add_alternative(html_content, subtype="html")

    chain = _provider_chain()

    # First pass: try only healthy providers
    preferred = [p for p in chain if not _is_on_cooldown(p)]
    # Fallback pass: if all are on cooldown, try them anyway
    providers_to_try = preferred if preferred else chain

    last_err: Optional[str] = None

    for provider in providers_to_try:
        try:
            cfg = _load_smtp(provider)
            _smtp_send(cfg, msg)
            _clear_provider_cooldown(provider)
            current_app.logger.info(
                "Email sent via provider=%s to=%s subject=%s",
                provider, to_email, subject
            )
            return provider, last_err

        except Exception as e:
            cooldown = _cooldown_seconds_for_error(e)
            _mark_provider_failed(provider, cooldown, str(e))
            last_err = f"{provider}: {e}"
            current_app.logger.exception(
                "Email failed via provider=%s to=%s subject=%s err=%s",
                provider, to_email, subject, e
            )

    raise EmailSendError(f"All providers failed. Last error: {last_err}")