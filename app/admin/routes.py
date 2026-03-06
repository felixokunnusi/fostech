# app/admin/routes.py

import time
from datetime import datetime, timedelta

from flask import render_template, request, flash, redirect, url_for, current_app, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import exists

from app.extensions import db
from app.models import User
from app.models.subscription import Subscription  # adjust if needed
from app.models.campaign_log import CampaignLog
from app.utils import admin_required, run_in_background
from app.auth.email import send_dynamic_template_email
from . import admin_bp
from .importer import import_questions_from_csv_file


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


def _send_campaign_job(
    campaign_id: int,
    target: str,
    limit: int,
    app_name: str,
    sender_name: str,
    dashboard_link: str,
    subscribe_link: str,
) -> None:
    """
    Background worker for campaigns.
    Uses local template IDs:
      - active_subscribers
      - active_non_subscribers
    """
    log = CampaignLog.query.get(campaign_id)
    if not log:
        current_app.logger.error("CampaignLog not found: id=%s", campaign_id)
        return

    try:
        current_app.logger.info(
            "Campaign %s thread started. target=%s limit=%s",
            campaign_id, target, limit
        )

        log.status = "running"
        log.started_at = datetime.utcnow()
        log.last_error = None
        db.session.commit()

        now = datetime.utcnow()
        total_sent = 0
        total_failed = 0
        total_targeted = 0

        def flush(force: bool = False) -> None:
            if force or (total_sent + total_failed) % 10 == 0:
                log.total_sent = total_sent
                log.total_failed = total_failed
                log.total_targeted = total_targeted
                db.session.commit()

        # Segment A: Active subscribers
        if target in ("subscribers", "both"):
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

            current_app.logger.info("Campaign %s: subs_users=%s", campaign_id, len(subs_users))

            total_targeted += len(subs_users)
            flush(force=True)

            for u in subs_users:
                try:
                    send_dynamic_template_email(
                        to_email=u.email,
                        template_id="active_subscribers",
                        dynamic_data={
                            "first_name": u.username,
                            "app_name": app_name,
                            "dashboard_link": dashboard_link,
                            "sender_name": sender_name,
                            "subject": f"{app_name}: Your premium access is active",
                            "text_fallback": f"Hello {u.username}\nDashboard: {dashboard_link}\n— {sender_name}",
                        },
                    )
                    total_sent += 1
                except Exception as e:
                    current_app.logger.exception(
                        "Subscriber campaign failed: user_id=%s email=%s",
                        u.id, u.email
                    )
                    total_failed += 1
                    log.last_error = str(e)

                flush()
                time.sleep(0.15)

        # Segment B: Verified users who are NOT active subscribers
        if target in ("non_subscribers", "both"):
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

            current_app.logger.info("Campaign %s: non_sub_users=%s", campaign_id, len(non_sub_users))

            total_targeted += len(non_sub_users)
            flush(force=True)

            for u in non_sub_users:
                try:
                    send_dynamic_template_email(
                        to_email=u.email,
                        template_id="active_non_subscribers",
                        dynamic_data={
                            "first_name": u.username,
                            "app_name": app_name,
                            "subscribe_link": subscribe_link,
                            "sender_name": sender_name,
                            "subject": f"{app_name}: Unlock premium practice",
                            "text_fallback": f"Hello {u.username}\nSubscribe: {subscribe_link}\n— {sender_name}",
                        },
                    )
                    total_sent += 1
                except Exception as e:
                    current_app.logger.exception(
                        "Non-subscriber campaign failed: user_id=%s email=%s",
                        u.id, u.email
                    )
                    total_failed += 1
                    log.last_error = str(e)

                flush()
                time.sleep(0.15)

        log.total_sent = total_sent
        log.total_failed = total_failed
        log.total_targeted = total_targeted
        log.status = "completed"
        log.finished_at = datetime.utcnow()
        db.session.commit()

        current_app.logger.info(
            "Campaign %s finished: status=%s sent=%s failed=%s targeted=%s last_error=%s",
            campaign_id, log.status, log.total_sent, log.total_failed, log.total_targeted, log.last_error
        )

    except Exception as e:
        current_app.logger.exception("Campaign job crashed: %s", e)
        log.status = "failed"
        log.last_error = str(e)
        log.finished_at = datetime.utcnow()
        db.session.commit()
    finally:
        db.session.remove()


@admin_bp.route("/campaigns/send", methods=["POST"])
@login_required
@admin_required
def send_campaigns():
    # Prevent accidental double send (5 min cooldown)
    last_sent = session.get("last_campaign_sent")
    now = datetime.utcnow()

    if last_sent:
        try:
            last_sent_dt = datetime.fromisoformat(last_sent)
            if now - last_sent_dt < timedelta(minutes=5):
                flash("Campaign was sent recently. Please wait before sending again.", "warning")
                return redirect(url_for("dashboard.index"))
        except ValueError:
            session.pop("last_campaign_sent", None)

    session["last_campaign_sent"] = now.isoformat()

    target = request.form.get("target", "both")
    if target not in ("subscribers", "non_subscribers", "both"):
        target = "both"

    cfg_limit = current_app.config.get("WEEKLY_EMAIL_LIMIT", 200)
    try:
        cfg_limit = int(cfg_limit)
    except Exception:
        cfg_limit = 200
    limit = min(max(cfg_limit, 1), 500)

    app_name = current_app.config.get("APP_NAME", "FOTMASTech CBT App")
    sender_name = current_app.config.get("SENDER_NAME", "Felix")

    # Build links here while request context is active
    dashboard_link = url_for("dashboard.index", _external=True)
    subscribe_link = url_for("subscription.start_subscription", _external=True)

    log = CampaignLog(
        created_by_user_id=getattr(current_user, "id", None),
        target=target,
        status="queued",
        limit_each=limit,
        created_at=datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()

    run_in_background(
        _send_campaign_job,
        log.id,
        target,
        limit,
        app_name,
        sender_name,
        dashboard_link,
        subscribe_link,
    )

    flash(f"Campaign queued (ID #{log.id}). Sending in background…", "success")
    return redirect(url_for("dashboard.index"))


@admin_bp.route("/campaigns/test", methods=["POST"])
@login_required
@admin_required
def test_email():
    app_name = current_app.config.get("APP_NAME", "FOTMASTech CBT App")
    sender_name = current_app.config.get("SENDER_NAME", "Admin")
    dashboard_link = url_for("dashboard.index", _external=True)

    send_dynamic_template_email(
        to_email=current_user.email,
        template_id="active_subscribers",
        dynamic_data={
            "first_name": current_user.username,
            "app_name": app_name,
            "dashboard_link": dashboard_link,
            "sender_name": sender_name,
            "subject": "Test Email",
            "text_fallback": "Test Email",
        },
    )

    flash("Test email attempted. Check inbox/spam and logs.", "info")
    return redirect(url_for("dashboard.index"))