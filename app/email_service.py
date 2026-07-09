# app/email_service.py

from __future__ import annotations

import smtplib
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from typing import Optional

from flask import current_app


class EmailSendError(RuntimeError):
    """Raised when all configured email providers fail."""


@dataclass(frozen=True)
class SMTPConfig:
    name: str
    host: str
    port: int
    username: str
    password: str


# Store provider cooldown expiry times in memory.
# This resets whenever the Flask process restarts.
_PROVIDER_COOLDOWNS: dict[str, float] = {}

DEFAULT_SMTP_TIMEOUT = 20
DEFAULT_COOLDOWN_SECONDS = 600


def _clean(value: object) -> str:
    """Convert a configuration value to a stripped string."""
    if value is None:
        return ""

    return str(value).strip()


def _as_int(value: object, default: int) -> int:
    """Convert a value to int and fall back safely."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _provider_chain() -> list[str]:
    """
    Return the configured provider order.

    EMAIL_PROVIDER_CHAIN takes priority. If it is empty,
    EMAIL_PROVIDER is used.
    """
    configured_chain = _clean(
        current_app.config.get("EMAIL_PROVIDER_CHAIN")
    )

    if configured_chain:
        providers = [
            provider.strip().lower()
            for provider in configured_chain.split(",")
            if provider.strip()
        ]
    else:
        default_provider = _clean(
            current_app.config.get("EMAIL_PROVIDER", "zoho")
        ).lower()

        providers = [default_provider] if default_provider else ["zoho"]

    # Remove duplicates while preserving order.
    return list(dict.fromkeys(providers))


def _get_provider_config(provider: str) -> SMTPConfig:
    """Build SMTP configuration for a named provider."""
    provider = provider.strip().lower()

    if provider == "zoho":
        return SMTPConfig(
            name="zoho",
            host=_clean(
                current_app.config.get(
                    "ZOHO_SMTP_HOST",
                    "smtppro.zoho.com",
                )
            ),
            port=_as_int(
                current_app.config.get("ZOHO_SMTP_PORT"),
                587,
            ),
            username=_clean(
                current_app.config.get("ZOHO_SMTP_USERNAME")
            ),
            password=_clean(
                current_app.config.get("ZOHO_SMTP_PASSWORD")
            ),
        )

    if provider == "brevo":
        return SMTPConfig(
            name="brevo",
            host=_clean(
                current_app.config.get(
                    "BREVO_SMTP_HOST",
                    "smtp-relay.brevo.com",
                )
            ),
            port=_as_int(
                current_app.config.get("BREVO_SMTP_PORT"),
                587,
            ),
            username=_clean(
                current_app.config.get("BREVO_SMTP_USERNAME")
            ),
            password=_clean(
                current_app.config.get("BREVO_SMTP_PASSWORD")
            ),
        )

    if provider == "mailersend":
        return SMTPConfig(
            name="mailersend",
            host=_clean(
                current_app.config.get(
                    "MAILERSEND_SMTP_HOST",
                    "smtp.mailersend.net",
                )
            ),
            port=_as_int(
                current_app.config.get("MAILERSEND_SMTP_PORT"),
                587,
            ),
            username=_clean(
                current_app.config.get("MAILERSEND_SMTP_USERNAME")
            ),
            password=_clean(
                current_app.config.get("MAILERSEND_SMTP_PASSWORD")
            ),
        )

    raise EmailSendError(
        f"Unsupported email provider: {provider}"
    )


def _validate_provider_config(cfg: SMTPConfig) -> None:
    """Ensure the provider has the required SMTP settings."""
    missing: list[str] = []

    if not cfg.host:
        missing.append("host")

    if not cfg.port:
        missing.append("port")

    if not cfg.username:
        missing.append("username")

    if not cfg.password:
        missing.append("password")

    if missing:
        fields = ", ".join(missing)

        raise EmailSendError(
            f"{cfg.name} SMTP configuration is missing: {fields}"
        )


def _get_sender() -> tuple[str, str]:
    """
    Return sender name and sender email.

    Accepts either:
        admin@fotmas.site

    or:
        FOSTech <admin@fotmas.site>
    """
    configured_sender = _clean(
        current_app.config.get("MAIL_DEFAULT_SENDER")
    )

    if not configured_sender:
        configured_sender = _clean(
            current_app.config.get("MAIL_USERNAME")
        )

    if not configured_sender:
        raise EmailSendError(
            "MAIL_DEFAULT_SENDER is missing. "
            "Set it in .env or the deployment environment variables."
        )

    parsed_name, parsed_email = parseaddr(configured_sender)

    if not parsed_email:
        raise EmailSendError(
            "MAIL_DEFAULT_SENDER does not contain a valid email address."
        )

    sender_name = (
        parsed_name
        or _clean(current_app.config.get("APP_NAME"))
        or _clean(current_app.config.get("SENDER_NAME"))
        or "FOSTech CBT App"
    )

    return sender_name, parsed_email


def _build_message(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> EmailMessage:
    """Create an email with plain-text and HTML alternatives."""
    recipient = _clean(to_email)
    subject = _clean(subject)

    if not recipient:
        raise EmailSendError("Recipient email address is missing.")

    if not subject:
        raise EmailSendError("Email subject is missing.")

    sender_name, sender_email = _get_sender()

    message = EmailMessage()
    message["From"] = formataddr((sender_name, sender_email))
    message["To"] = recipient
    message["Subject"] = subject

    plain_text = _clean(text_content)

    if not plain_text:
        plain_text = (
            "This email contains HTML content. "
            "Please view it using an HTML-compatible email client."
        )

    message.set_content(plain_text)

    if html_content:
        message.add_alternative(
            str(html_content),
            subtype="html",
        )

    return message


def _smtp_timeout() -> int:
    """Return the configured SMTP connection timeout."""
    return _as_int(
        current_app.config.get(
            "SMTP_TIMEOUT_SECONDS",
            DEFAULT_SMTP_TIMEOUT,
        ),
        DEFAULT_SMTP_TIMEOUT,
    )


def _smtp_send(cfg: SMTPConfig, message: EmailMessage) -> None:
    """
    Send an email using the correct connection method.

    Port 465:
        Implicit TLS using SMTP_SSL.

    Other ports, including 587 and 2525:
        SMTP connection upgraded with STARTTLS.
    """
    _validate_provider_config(cfg)

    timeout = _smtp_timeout()
    tls_context = ssl.create_default_context()

    if cfg.port == 465:
        with smtplib.SMTP_SSL(
            cfg.host,
            cfg.port,
            timeout=timeout,
            context=tls_context,
        ) as server:
            server.login(cfg.username, cfg.password)
            server.send_message(message)

        return

    with smtplib.SMTP(
        cfg.host,
        cfg.port,
        timeout=timeout,
    ) as server:
        server.ehlo()
        server.starttls(context=tls_context)
        server.ehlo()
        server.login(cfg.username, cfg.password)
        server.send_message(message)


def _cooldown_seconds() -> int:
    """Return the provider failure cooldown duration."""
    return _as_int(
        current_app.config.get(
            "EMAIL_PROVIDER_COOLDOWN_SECONDS",
            DEFAULT_COOLDOWN_SECONDS,
        ),
        DEFAULT_COOLDOWN_SECONDS,
    )


def _provider_is_on_cooldown(provider: str) -> bool:
    """Return True while a provider is temporarily unavailable."""
    cooldown_until = _PROVIDER_COOLDOWNS.get(provider, 0)
    return cooldown_until > time.monotonic()


def _put_provider_on_cooldown(
    provider: str,
    reason: object,
) -> None:
    """Temporarily skip a provider after an SMTP failure."""
    cooldown_seconds = _cooldown_seconds()

    _PROVIDER_COOLDOWNS[provider] = (
        time.monotonic() + cooldown_seconds
    )

    current_app.logger.warning(
        "Email provider put on cooldown: "
        "provider=%s cooldown_seconds=%s reason=%s",
        provider,
        cooldown_seconds,
        reason,
    )


def _clear_provider_cooldown(provider: str) -> None:
    """Remove cooldown after a successful delivery."""
    _PROVIDER_COOLDOWNS.pop(provider, None)


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> bool:
    """
    Send an email using the configured provider chain.

    Example:
        EMAIL_PROVIDER_CHAIN=zoho,brevo,mailersend

    Returns True when delivery succeeds.

    Raises EmailSendError when every configured provider fails.
    """
    message = _build_message(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )

    providers = _provider_chain()

    if not providers:
        raise EmailSendError(
            "No email providers are configured."
        )

    last_error: Optional[Exception] = None
    attempted_provider = False

    for provider in providers:
        if _provider_is_on_cooldown(provider):
            current_app.logger.warning(
                "Email provider skipped because it is on cooldown: "
                "provider=%s",
                provider,
            )
            continue

        attempted_provider = True

        try:
            cfg = _get_provider_config(provider)
            _smtp_send(cfg, message)

            _clear_provider_cooldown(provider)

            current_app.logger.info(
                "Email sent successfully: "
                "provider=%s to=%s subject=%s",
                provider,
                to_email,
                subject,
            )

            return True

        except Exception as exc:
            last_error = exc
            _put_provider_on_cooldown(provider, exc)

            current_app.logger.exception(
                "Email failed via provider=%s "
                "to=%s subject=%s err=%s",
                provider,
                to_email,
                subject,
                exc,
            )

    if not attempted_provider:
        raise EmailSendError(
            "All configured email providers are currently on cooldown."
        )

    error_message = (
        str(last_error)
        if last_error is not None
        else "Unknown email delivery error"
    )

    raise EmailSendError(
        f"All providers failed. Last error: {error_message}"
    )