from datetime import datetime
from flask import current_app

from app.extensions import db
from app.models import User
from app.models.subscription import Subscription
from app.auth.email import (
    get_active_subscribers,
    get_active_users_not_subscribers,
    send_dynamic_template_email,
)

def register_cli(app):
    @app.cli.command("send_weekly_emails")
    def send_weekly_emails():
        now = datetime.utcnow()

        tmpl_subs = current_app.config.get("SENDGRID_TMPL_ACTIVE_SUBSCRIBERS")
        tmpl_non = current_app.config.get("SENDGRID_TMPL_ACTIVE_NON_SUBSCRIBERS")
        app_name = current_app.config.get("APP_NAME", "FOTMASTech CBT App")
        sender_name = current_app.config.get("SENDER_NAME", "Admin")
        base_url = (current_app.config.get("BASE_URL") or "").rstrip("/")
        limit = int(current_app.config.get("WEEKLY_EMAIL_LIMIT", 200))

        if not tmpl_subs or not tmpl_non:
            raise RuntimeError("Missing SendGrid weekly template IDs in config.")

        dashboard_link = f"{base_url}/dashboard" if base_url else ""
        subscribe_link = f"{base_url}/subscription/start" if base_url else ""

        # Active subscribers
        subs_users = get_active_subscribers(db, User, Subscription, now=now, limit=limit)
        sent_subs = failed_subs = 0
        for u in subs_users:
            try:
                send_dynamic_template_email(
                    to_email=u.email,
                    template_id=tmpl_subs,
                    dynamic_data={
                        "first_name": u.username,
                        "app_name": app_name,
                        "dashboard_link": dashboard_link,
                        "sender_name": sender_name,
                    },
                )
                sent_subs += 1
            except Exception:
                failed_subs += 1
                current_app.logger.exception("Weekly subs failed to %s", u.email)

        # Active verified non-subscribers
        non_users = get_active_users_not_subscribers(db, User, Subscription, now=now, limit=limit)
        sent_non = failed_non = 0
        for u in non_users:
            try:
                send_dynamic_template_email(
                    to_email=u.email,
                    template_id=tmpl_non,
                    dynamic_data={
                        "first_name": u.username,
                        "app_name": app_name,
                        "subscribe_link": subscribe_link,
                        "sender_name": sender_name,
                    },
                )
                sent_non += 1
            except Exception:
                failed_non += 1
                current_app.logger.exception("Weekly non-subs failed to %s", u.email)

        current_app.logger.info(
            "Weekly emails done. subs_sent=%s subs_failed=%s non_sent=%s non_failed=%s",
            sent_subs, failed_subs, sent_non, failed_non
        )