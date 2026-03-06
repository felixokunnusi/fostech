import logging
from datetime import datetime

from flask import current_app, render_template, url_for

from app.email_service import send_email  # SMTP sender


logger = logging.getLogger(__name__)


# ---------------------------
# Internal: send helper
# ---------------------------

def _get_sender() -> str:
    sender = (
        current_app.config.get("MAIL_DEFAULT_SENDER")
        or current_app.config.get("MAIL_USERNAME")
    )
    if not sender:
        raise RuntimeError(
            "MAIL_DEFAULT_SENDER is missing. Set it in .env / Render env vars."
        )
    return sender


def _send_message(to_email: str, subject: str, html_content: str, text_content: str | None = None) -> None:
    """
    Sends an email through the SMTP-based send_email helper.
    Raises on failure.
    """
    try:
        sender = _get_sender()

        # Assumes app.email_service.send_email signature:
        # send_email(to_email, subject, html_content, text_content=None, from_email=None)
        try:
            send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                from_email=sender,
            )
        except TypeError:
            # Fallback in case your helper only accepts 4 args
            send_email(to_email, subject, html_content, text_content)

        current_app.logger.info(
            "Email sent successfully via SMTP. to=%s subject=%s",
            to_email,
            subject,
        )

    except Exception as e:
        logger.exception(
            "SMTP email send failed. to=%s subject=%s error=%s",
            to_email,
            subject,
            e,
        )
        raise


# ---------------------------
# 1) Existing emails
# ---------------------------

def send_confirmation_email(user) -> None:
    """
    Sends email confirmation code + link.
    """
    confirm_url = url_for("auth.confirm_email", code=user.email_confirm_code, _external=True)

    html_content = f"""
    <p>Hello {user.username},</p>
    <p>Your confirmation code is:</p>
    <h2>{user.email_confirm_code}</h2>
    <p>Or click the link below:</p>
    <p><a href="{confirm_url}">Confirm Email</a></p>
    <p>This code expires in 10 minutes.</p>
    """

    text_content = (
        f"Hello {user.username},\n\n"
        f"Your confirmation code is: {user.email_confirm_code}\n\n"
        f"Confirm your email here: {confirm_url}\n\n"
        f"This code expires in 10 minutes."
    )

    _send_message(
        to_email=user.email,
        subject="Confirm your email",
        html_content=html_content,
        text_content=text_content,
    )


def send_password_reset_email(user) -> None:
    """
    Sends password reset link.
    """
    reset_url = url_for("auth.reset_password", token=user.reset_token, _external=True)

    html_content = f"""
    <p>Hello {user.username},</p>
    <p>You requested a password reset.</p>
    <p><a href="{reset_url}">Click here to reset your password</a></p>
    <p>This link expires in 30 minutes.</p>
    """

    text_content = (
        f"Hello {user.username},\n\n"
        f"You requested a password reset.\n"
        f"Reset your password here: {reset_url}\n\n"
        f"This link expires in 30 minutes."
    )

    _send_message(
        to_email=user.email,
        subject="Reset your password",
        html_content=html_content,
        text_content=text_content,
    )


# ---------------------------
# 2) Reusable campaign senders
# ---------------------------

def send_html_email(to_email: str, subject: str, html_content: str, text_content: str | None = None) -> None:
    """
    Simple HTML email sender (no templates).
    """
    _send_message(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )


TEMPLATE_MAP = {
    "active_subscribers": "email/active_subscribers.html",
    "active_non_subscribers": "email/active_non_subscribers.html",
}

SUBJECT_MAP = {
    "active_subscribers": "Your premium access is active",
    "active_non_subscribers": "Unlock premium practice",
}


def send_dynamic_template_email(to_email: str, template_id: str, dynamic_data: dict) -> None:
    """
    Local-template email sender.
    'template_id' is a local key, not a SendGrid template id.
    """
    template_path = TEMPLATE_MAP.get(template_id)
    if not template_path:
        raise RuntimeError(
            f"Unknown template_id '{template_id}'. Expected one of: {list(TEMPLATE_MAP)}"
        )

    subject = dynamic_data.get("subject") or SUBJECT_MAP.get(template_id, "Notification")
    html = render_template(template_path, **dynamic_data)
    text = dynamic_data.get("text_fallback")

    _send_message(
        to_email=to_email,
        subject=subject,
        html_content=html,
        text_content=text,
    )


# ---------------------------
# 3) Segment queries + campaigns
# ---------------------------

def get_active_subscribers(db, User, Subscription, now=None, limit=500):
    """
    Active subscribers = confirmed + expires_at in future.
    Returns a list of User objects.
    """
    now = now or datetime.utcnow()

    return (
        db.session.query(User)
        .join(Subscription, Subscription.user_id == User.id)
        .filter(
            Subscription.is_confirmed.is_(True),
            Subscription.expires_at.isnot(None),
            Subscription.expires_at > now,
        )
        .distinct()
        .order_by(User.id.desc())
        .limit(limit)
        .all()
    )


def get_active_users_not_subscribers(db, User, Subscription, now=None, limit=500):
    """
    Active users (email verified) who do NOT have an active subscription.
    Returns a list of User objects.
    """
    now = now or datetime.utcnow()

    active_sub_exists = (
        db.session.query(Subscription.id)
        .filter(
            Subscription.user_id == User.id,
            Subscription.is_confirmed.is_(True),
            Subscription.expires_at.isnot(None),
            Subscription.expires_at > now,
        )
        .exists()
    )

    return (
        db.session.query(User)
        .filter(
            User.is_email_verified.is_(True),
            ~active_sub_exists,
        )
        .order_by(User.id.desc())
        .limit(limit)
        .all()
    )


def send_campaign_to_active_subscribers(db, User, Subscription, template_id: str, app_name: str, sender_name: str):
    """
    Sends a template email to all active subscribers.
    """
    users = get_active_subscribers(db, User, Subscription)
    dashboard_link = url_for("dashboard.index", _external=True)

    for u in users:
        send_dynamic_template_email(
            to_email=u.email,
            template_id=template_id,
            dynamic_data={
                "first_name": u.username,
                "app_name": app_name,
                "dashboard_link": dashboard_link,
                "sender_name": sender_name,
            },
        )


def send_campaign_to_active_users_not_subscribers(db, User, Subscription, template_id: str, app_name: str, sender_name: str):
    """
    Sends a template email to verified users who are not active subscribers.
    """
    users = get_active_users_not_subscribers(db, User, Subscription)
    subscribe_link = url_for("subscription.start_subscription", _external=True)

    for u in users:
        send_dynamic_template_email(
            to_email=u.email,
            template_id=template_id,
            dynamic_data={
                "first_name": u.username,
                "app_name": app_name,
                "subscribe_link": subscribe_link,
                "sender_name": sender_name,
            },
        )