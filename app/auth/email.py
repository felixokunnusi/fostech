import logging
import os
from flask import current_app, url_for
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from urllib.error import URLError
from datetime import datetime




# ---------------------------
# Internal: send helper
# ---------------------------

def _get_sender() -> str:
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME")
    if not sender:
        raise RuntimeError("MAIL_DEFAULT_SENDER is missing. Set it in .env / Render env vars.")
    return sender


def _get_sendgrid_client() -> SendGridAPIClient:
    api_key = current_app.config.get("SENDGRID_API_KEY")
    if not api_key:
        raise RuntimeError("SENDGRID_API_KEY is missing. Set it in .env / Render env vars.")
    return SendGridAPIClient(api_key)


def _send_message(message: Mail) -> None:
    """
    Sends a SendGrid Mail message. Logs useful error details.
    Raises on failure.
    """
    try:
        sg = _get_sendgrid_client()
        resp = sg.send(message)

        current_app.logger.info(
            "SendGrid send result: status=%s headers=%s body=%s",
            resp.status_code, resp.headers, resp.body
        )

        # SendGrid typically returns 202 on success
        if resp.status_code not in (200, 202):
            logging.error(
                "SendGrid failed. Status=%s Body=%s Headers=%s",
                resp.status_code, resp.body, resp.headers
            )
            raise RuntimeError(f"SendGrid rejected email. status={resp.status_code}")

    except Exception as e:
        body = getattr(e, "body", None)
        status = getattr(e, "status_code", None)
        logging.exception("SendGrid error: status=%s body=%s error=%s", status, body, e)
        raise


# ---------------------------
# 1) Existing emails (fixed)
# ---------------------------

def send_confirmation_email(user) -> None:
    """
    Sends email confirmation code + link.
    """
    confirm_url = url_for("auth.confirm_email", code=user.email_confirm_code, _external=True)
    sender = _get_sender()

    message = Mail(
        from_email=sender,
        to_emails=user.email,
        subject="Confirm your email",
        html_content=f"""
        <p>Hello {user.username},</p>
        <p>Your confirmation code is:</p>
        <h2>{user.email_confirm_code}</h2>
        <p>Or click the link below:</p>
        <p><a href="{confirm_url}">Confirm Email</a></p>
        <p>This code expires in 10 minutes.</p>
        """
    )

    _send_message(message)


def send_password_reset_email(user) -> None:
    """
    Sends password reset link.
    """
    reset_url = url_for("auth.reset_password", token=user.reset_token, _external=True)
    sender = _get_sender()

    message = Mail(
        from_email=sender,
        to_emails=user.email,
        subject="Reset your password",
        html_content=f"""
        <p>Hello {user.username},</p>
        <p>You requested a password reset.</p>
        <p><a href="{reset_url}">Click here to reset your password</a></p>
        <p>This link expires in 30 minutes.</p>
        """
    )

    _send_message(message)


# ---------------------------
# 2) Reusable campaign senders
# ---------------------------

def send_html_email(to_email: str, subject: str, html_content: str) -> None:
    """
    Simple HTML email sender (no templates).
    """
    sender = _get_sender()

    message = Mail(
        from_email=sender,
        to_emails=to_email,
        subject=subject,
        html_content=html_content
    )

    _send_message(message)


def send_dynamic_template_email(to_email: str, template_id: str, dynamic_data: dict) -> None:
    """
    SendGrid Dynamic Template sender.
    template_id like: 'd-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    dynamic_data dict keys should match your SendGrid template placeholders.
    """
    sender = _get_sender()

    message = Mail(from_email=sender, to_emails=to_email)
    message.template_id = template_id
    message.dynamic_template_data = dynamic_data

    _send_message(message)


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
        .distinct(User.id)
        .order_by(User.id.desc())
        .limit(limit)
        .all()
    )


def get_active_users_not_subscribers(db, User, Subscription, now=None, limit=500):
    """
    Active users (email verified) who do NOT have an active subscription.
    Returns a list of User objects.
    """
    from sqlalchemy import exists

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
    Sends a dynamic template email to all active subscribers.
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
            }
        )


def send_campaign_to_active_users_not_subscribers(db, User, Subscription, template_id: str, app_name: str, sender_name: str):
    """
    Sends a dynamic template email to verified users who are not active subscribers.
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
            }
        )