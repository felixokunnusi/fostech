# app/admin/routes.py

import time
import uuid
from decimal import Decimal, ROUND_HALF_UP
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


Q = Decimal("0.01")


def _money(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Q, rounding=ROUND_HALF_UP)


def _default_subscription_amount_naira() -> Decimal:
    """Return configured subscription amount in naira.

    SUBSCRIPTION_AMOUNT is currently stored in kobo in your payment flow.
    """
    amount_kobo = current_app.config.get("SUBSCRIPTION_AMOUNT", 1000000)
    return _money(Decimal(str(amount_kobo)) / Decimal("100"))


def _parse_days(value, default: int = 366) -> int:
    try:
        days = int(value or default)
    except (TypeError, ValueError):
        days = default
    return max(1, min(days, 3660))


@admin_bp.route("/subscriptions", methods=["GET"])
@login_required
@admin_required
def manage_subscriptions():
    """Admin page for finding users and manually updating subscription access."""
    q = (request.args.get("q") or "").strip()
    now = datetime.utcnow()

    users = []
    if q:
        like = f"%{q}%"
        users = (
            User.query
            .filter((User.email.ilike(like)) | (User.username.ilike(like)))
            .order_by(User.id.desc())
            .limit(50)
            .all()
        )
    else:
        users = (
            User.query
            .order_by(User.id.desc())
            .limit(50)
            .all()
        )

    latest_sub_by_user = {}
    active_sub_by_user = {}

    if users:
        user_ids = [u.id for u in users]
        subs = (
            Subscription.query
            .filter(Subscription.user_id.in_(user_ids))
            .order_by(Subscription.user_id.asc(), Subscription.id.desc())
            .all()
        )

        for sub in subs:
            latest_sub_by_user.setdefault(sub.user_id, sub)
            if sub.is_confirmed and sub.expires_at and sub.expires_at > now:
                active_sub_by_user.setdefault(sub.user_id, sub)

    return render_template(
        "admin/subscriptions.html",
        q=q,
        users=users,
        latest_sub_by_user=latest_sub_by_user,
        active_sub_by_user=active_sub_by_user,
        default_amount=_default_subscription_amount_naira(),
        default_days=366,
        now=now,
    )


@admin_bp.route("/subscriptions/<int:user_id>/activate", methods=["POST"])
@login_required
@admin_required
def manually_activate_subscription(user_id: int):
    """Manually grant premium access after a verified payment or admin approval."""
    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("admin.manage_subscriptions"))

    days = _parse_days(request.form.get("days"), default=366)
    amount = _money(request.form.get("amount") or _default_subscription_amount_naira())
    payment_reference = (request.form.get("payment_reference") or "").strip()
    now = datetime.utcnow()

    existing_active = (
        Subscription.query
        .filter(
            Subscription.user_id == user.id,
            Subscription.is_confirmed.is_(True),
            Subscription.expires_at.isnot(None),
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
        .first()
    )
    if existing_active:
        flash(
            f"{user.email} already has active access until {existing_active.expires_at.strftime('%Y-%m-%d')}.",
            "warning",
        )
        return redirect(url_for("admin.manage_subscriptions", q=user.email))

    # Prefer activating the latest pending Paystack subscription, because this fixes failed redirects.
    subscription = (
        Subscription.query
        .filter_by(user_id=user.id, is_confirmed=False)
        .order_by(Subscription.id.desc())
        .first()
    )

    if not subscription:
        manual_reference = payment_reference or f"MANUAL_{uuid.uuid4().hex}"
        subscription = Subscription(
            user_id=user.id,
            amount=float(amount),
            currency="NGN",
            payment_provider="manual",
            reference=manual_reference,
            payment_reference=payment_reference or manual_reference,
        )
        db.session.add(subscription)
    else:
        subscription.amount = float(amount)
        if not subscription.currency:
            subscription.currency = "NGN"
        if not subscription.payment_provider:
            subscription.payment_provider = "manual"
        if payment_reference and not subscription.payment_reference:
            subscription.payment_reference = payment_reference

    subscription.is_confirmed = True
    subscription.paid_at = now
    subscription.set_expiration(days=days)

    try:
        db.session.commit()

        # Give referral bonus once. The service already prevents duplicate earning per subscription.
        from app.services.referral import handle_referral_bonus
        handle_referral_bonus(subscription)

        flash(
            f"Premium access activated for {user.email} until {subscription.expires_at.strftime('%Y-%m-%d')}.",
            "success",
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Manual subscription activation failed")
        flash(f"Could not activate subscription: {e}", "danger")

    return redirect(url_for("admin.manage_subscriptions", q=user.email))


@admin_bp.route("/subscriptions/<int:user_id>/deactivate", methods=["POST"])
@login_required
@admin_required
def manually_deactivate_subscription(user_id: int):
    """Remove active premium access if it was granted by mistake."""
    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("admin.manage_subscriptions"))

    now = datetime.utcnow()
    active_sub = (
        Subscription.query
        .filter(
            Subscription.user_id == user.id,
            Subscription.is_confirmed.is_(True),
            Subscription.expires_at.isnot(None),
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
        .first()
    )

    if not active_sub:
        flash(f"{user.email} has no active subscription to deactivate.", "warning")
        return redirect(url_for("admin.manage_subscriptions", q=user.email))

    active_sub.is_confirmed = False
    active_sub.expires_at = now

    try:
        db.session.commit()
        flash(f"Premium access deactivated for {user.email}.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Manual subscription deactivation failed")
        flash(f"Could not deactivate subscription: {e}", "danger")

    return redirect(url_for("admin.manage_subscriptions", q=user.email))


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



def _render_campaign_content(content: str, **values) -> str:
    """Replace only approved dashboard placeholders in campaign HTML."""
    rendered = content or ""
    for key, value in values.items():
        rendered = rendered.replace(f"[[{key}]]", str(value or ""))
    return rendered



def _send_campaign_job(
    campaign_id: int,
    target: str,
    limit: int,
    app_name: str,
    sender_name: str,
    dashboard_link: str,
    subscribe_link: str,
    subscriber_subject: str,
    subscriber_content: str,
    non_subscriber_subject: str,
    non_subscriber_content: str,
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
                    personalised_content = _render_campaign_content(
                        subscriber_content,
                        first_name=u.username or "User",
                        app_name=app_name,
                        dashboard_link=dashboard_link,
                        subscribe_link=subscribe_link,
                        sender_name=sender_name,
                    )
                    send_dynamic_template_email(
                        to_email=u.email,
                        template_id="custom_campaign",
                        dynamic_data={
                            "subject": subscriber_subject,
                            "email_content": personalised_content,
                            "text_fallback": f"Hello {u.username or 'User'} - {dashboard_link}",
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
                    personalised_content = _render_campaign_content(
                        non_subscriber_content,
                        first_name=u.username or "User",
                        app_name=app_name,
                        dashboard_link=dashboard_link,
                        subscribe_link=subscribe_link,
                        sender_name=sender_name,
                    )
                    send_dynamic_template_email(
                        to_email=u.email,
                        template_id="custom_campaign",
                        dynamic_data={
                            "subject": non_subscriber_subject,
                            "email_content": personalised_content,
                            "text_fallback": f"Hello {u.username or 'User'} - {subscribe_link}",
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

    target = request.form.get("target", "both")
    if target not in ("subscribers", "non_subscribers", "both"):
        target = "both"

    cfg_limit = current_app.config.get("WEEKLY_EMAIL_LIMIT", 200)
    try:
        cfg_limit = int(cfg_limit)
    except Exception:
        cfg_limit = 200
    limit = min(max(cfg_limit, 1), 500)

    app_name = current_app.config.get("APP_NAME", "FOSTech CBT App")
    sender_name = current_app.config.get("SENDER_NAME", "Felix")

    subscriber_subject = (request.form.get("subscriber_subject") or "").strip()
    subscriber_content = (request.form.get("subscriber_content") or "").strip()
    non_subscriber_subject = (request.form.get("non_subscriber_subject") or "").strip()
    non_subscriber_content = (request.form.get("non_subscriber_content") or "").strip()

    if target in ("subscribers", "both") and (not subscriber_subject or not subscriber_content):
        flash("Subscriber email subject and content are required.", "danger")
        return redirect(url_for("dashboard.index"))

    if target in ("non_subscribers", "both") and (not non_subscriber_subject or not non_subscriber_content):
        flash("Non-subscriber email subject and content are required.", "danger")
        return redirect(url_for("dashboard.index"))

    # Start the cooldown only after the submitted campaign has passed validation.
    session["last_campaign_sent"] = now.isoformat()

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
        subscriber_subject,
        subscriber_content,
        non_subscriber_subject,
        non_subscriber_content,
    )

    flash(f"Campaign queued (ID #{log.id}). Sending in background…", "success")
    return redirect(url_for("dashboard.index"))


@admin_bp.route("/campaigns/test", methods=["POST"])
@login_required
@admin_required
def test_email():
    app_name = current_app.config.get("APP_NAME", "FOSTech CBT App")
    sender_name = current_app.config.get("SENDER_NAME", "Admin")
    dashboard_link = url_for("dashboard.index", _external=True)
    subscribe_link = url_for("subscription.start_subscription", _external=True)

    test_target = request.form.get("test_target", "non_subscribers")
    if test_target == "subscribers":
        subject = (request.form.get("subscriber_subject") or "").strip()
        content = (request.form.get("subscriber_content") or "").strip()
    else:
        subject = (request.form.get("non_subscriber_subject") or "").strip()
        content = (request.form.get("non_subscriber_content") or "").strip()

    if not subject or not content:
        flash("Enter the test email subject and content first.", "danger")
        return redirect(url_for("dashboard.index"))

    personalised_content = _render_campaign_content(
        content,
        first_name=current_user.username or "Admin",
        app_name=app_name,
        dashboard_link=dashboard_link,
        subscribe_link=subscribe_link,
        sender_name=sender_name,
    )

    send_dynamic_template_email(
        to_email=current_user.email,
        template_id="custom_campaign",
        dynamic_data={
            "subject": subject,
            "email_content": personalised_content,
            "text_fallback": "Campaign test email",
        },
    )

    flash("Test email sent. Check your inbox and spam folder.", "success")
    return redirect(url_for("dashboard.index"))

