import os
from flask import current_app, url_for
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from urllib.error import URLError
import logging

def send_confirmation_email(user):
    confirm_url = url_for(
        "auth.confirm_email",
        code=user.email_confirm_code,
        _external=True
    )

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
        sg = SendGridAPIClient(api_key=current_app.config["SENDGRID_API_KEY"])
        sg.send(message)

    except URLError:
        logging.exception("SendGrid network error")
        raise RuntimeError("Email service is temporarily unavailable.")

    except Exception:
        logging.exception("SendGrid unknown error")
        raise RuntimeError("Failed to send confirmation email.")

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
