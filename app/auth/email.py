import os
from flask import current_app, url_for
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from urllib.error import URLError
import logging

def send_confirmation_email(user):
    confirm_url = url_for("auth.confirm_email", code=user.email_confirm_code, _external=True)
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME")
    if not sender:
        raise RuntimeError("MAIL_DEFAULT_SENDER is missing. Set it in .env")


    message = Mail(
        from_email=current_app.config["MAIL_DEFAULT_SENDER"],
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

    try:
        api_key = current_app.config.get("SENDGRID_API_KEY")
        if not api_key:
            raise RuntimeError("SENDGRID_API_KEY is missing. Set it in .env or environment variables.")

        sg = SendGridAPIClient(api_key=api_key)
        resp = sg.send(message)

        # SendGrid typically returns 202 on success
        if resp.status_code not in (200, 202):
            logging.error("SendGrid failed. Status=%s Body=%s Headers=%s", resp.status_code, resp.body, resp.headers)
            raise RuntimeError("Failed to send confirmation email (SendGrid non-success status).")

    except Exception as e:
        # 🔥 This prints the real SendGrid error in your console/logs
        # Many SendGrid exceptions include .body with JSON error details
        body = getattr(e, "body", None)
        status = getattr(e, "status_code", None)
        logging.exception("SendGrid error: status=%s body=%s error=%s", status, body, e)
        raise RuntimeError("Failed to send confirmation email.")
    
    # catch success status
    resp = sg.send(message)
    current_app.logger.info(
    "SendGrid send result: status=%s headers=%s body=%s",
    resp.status_code, resp.headers, resp.body
    )

    if resp.status_code != 202:
        raise RuntimeError(f"SendGrid rejected email. status={resp.status_code}")

# Send password reset email
def send_password_reset_email(user):
    reset_url = url_for(
        "auth.reset_password",
        token=user.reset_token,
        _external=True
    )

    message = Mail(
        from_email=current_app.config["MAIL_DEFAULT_SENDER"],
        to_emails=user.email,
        subject="Reset your password",
        html_content=f"""
        <p>You requested a password reset.</p>
        <p>
            <a href="{reset_url}">Click here to reset your password</a>
        </p>
        <p>This link expires in 30 minutes.</p>
        """
    )

    sg = SendGridAPIClient(current_app.config["SENDGRID_API_KEY"])
    sg.send(message)
