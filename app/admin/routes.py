# app/admin/routes.py

from flask import render_template, request, flash, redirect, url_for, current_app, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import User
from app.models.subscription import Subscription  # adjust import if needed
from app.extensions import db
from app.utils import admin_required
from . import admin_bp
from .importer import import_questions_from_csv_file
from datetime import datetime, timedelta
from app.auth.email import send_dynamic_template_email  # from the email.py we updated
from app.auth.email import (
    send_campaign_to_active_subscribers,
    send_campaign_to_active_users_not_subscribers
)


ALLOWED_EXTENSIONS = {"csv"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_bp.route("/upload-questions", methods=["GET", "POST"])
@login_required
@admin_required
def upload_questions():
    if request.method == "GET":
        return render_template("admin/upload_questions.html")

    file = request.files.get("file")
    if not file or not file.filename:
        flash("Please select a CSV file.", "warning")
        return redirect(url_for("admin.upload_questions"))

    if not allowed_file(file.filename):
        flash("Only .csv files are allowed.", "danger")
        return redirect(url_for("admin.upload_questions"))

    filename = secure_filename(file.filename)

    try:
        summary = import_questions_from_csv_file(file)
    except Exception as e:
        flash(f"Import failed: {e}", "danger")
        return redirect(url_for("admin.upload_questions"))

    if summary and summary.get("errors"):
        flash(f"Imported with errors from {filename}. See details below.", "warning")
    else:
        flash(f"✅ Import successful: {filename}", "success")

    return render_template("admin/upload_questions.html", summary=summary, filename=filename)


### Send Campaign ###
@admin_bp.route("/campaigns/send", methods=["POST"])
@login_required
@admin_required
def send_campaigns():
     # 🔒 Prevent accidental double send (5 min cooldown)
    last_sent = session.get("last_campaign_sent")
    now = datetime.utcnow()

    if last_sent:
        last_sent_dt = datetime.fromisoformat(last_sent)
        if now - last_sent_dt < timedelta(minutes=5):
            flash("Campaign was sent recently. Please wait before sending again.", "warning")
            return redirect(url_for("dashboard.index"))

    # Save timestamp BEFORE sending
    session["last_campaign_sent"] = now.isoformat()

    target = request.form.get("target", "both")  # subscribers | non_subscribers | both
    limit = 200
    now = datetime.utcnow()

    tmpl_subs = current_app.config.get("SENDGRID_TMPL_ACTIVE_SUBSCRIBERS")
    tmpl_non = current_app.config.get("SENDGRID_TMPL_ACTIVE_NON_SUBSCRIBERS")

    app_name = current_app.config.get("APP_NAME", "FOTMASTech CBT App")
    sender_name = current_app.config.get("SENDER_NAME", "Felix")

    # --- Segment A: Active subscribers (confirmed + not expired) ---
    if target in ("subscribers", "both"):
        if not tmpl_subs:
            flash("Missing SENDGRID_TMPL_ACTIVE_SUBSCRIBERS in config.", "danger")
            return redirect(url_for("dashboard.index"))

        subs_users = (
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

        dashboard_link = url_for("dashboard.index", _external=True)

        sent = 0
        for u in subs_users:
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
            sent += 1

        flash(f"Subscriber campaign sent to {sent} user(s).", "success")

    # --- Segment B: Verified users who are NOT active subscribers ---
    if target in ("non_subscribers", "both"):
        if not tmpl_non:
            flash("Missing SENDGRID_TMPL_ACTIVE_NON_SUBSCRIBERS in config.", "danger")
            return redirect(url_for("dashboard.index"))

        from sqlalchemy import exists

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

        non_sub_users = (
            db.session.query(User)
            .filter(
                User.is_email_verified.is_(True),
                ~active_sub_exists,
            )
            .order_by(User.id.desc())
            .limit(limit)
            .all()
        )

        subscribe_link = url_for("subscription.start_subscription", _external=True)

        sent = 0
        for u in non_sub_users:
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
            sent += 1

        flash(f"Non-subscriber campaign sent to {sent} user(s).", "success")

    return redirect(url_for("dashboard.index"))