from datetime import datetime
from flask import render_template, url_for
from flask_login import login_required, current_user
from sqlalchemy import func

from . import dashboard_bp
from app.extensions import db
from app.models import User, ReferralEarning
from app.models.quiz import QuizSession


@dashboard_bp.route("/")
@login_required
def index():
    referral_link = url_for("auth.register", ref=current_user.referral_code, _external=True)

    referral_count = (
        db.session.query(func.count(User.id))
        .filter(User.referred_by == current_user.referral_code)
        .scalar()
        or 0
    )

    total_earnings = (
        db.session.query(func.coalesce(func.sum(ReferralEarning.amount), 0))
        .filter(ReferralEarning.referrer_id == current_user.id)
        .scalar()
        or 0
    )

    referred_users = (
        db.session.query(
            User.username,
            User.email,
            func.coalesce(func.sum(ReferralEarning.amount), 0).label("earned")
        )
        .outerjoin(ReferralEarning, ReferralEarning.referred_user_id == User.id)
        .filter(User.referred_by == current_user.referral_code)
        .group_by(User.id, User.username, User.email)
        .order_by(func.coalesce(func.sum(ReferralEarning.amount), 0).desc())
        .limit(200)
        .all()
    )

    active_session = (
        QuizSession.query
        .filter_by(user_id=current_user.id, is_submitted=False)
        .order_by(QuizSession.started_at.desc())
        .first()
    )

    if (
        active_session
        and active_session.mode == "exam"
        and active_session.expires_at
        and datetime.utcnow() > active_session.expires_at
    ):
        active_session.is_submitted = True
        active_session.completed_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        active_session = None

    # Admin data (LIMITED)
    from app.models import Subscription
    subscribers = []
    active_users = []

    if getattr(current_user, "is_admin", False):
        subscribers = (
            db.session.query(User.username, User.email, Subscription.paid_at)
            .join(Subscription, Subscription.user_id == User.id)
            .filter(Subscription.is_confirmed.is_(True))
            .order_by(Subscription.id.desc())
            .limit(200)
            .all()
        )

        active_users = (
            db.session.query(User.username, User.email)
            .filter(User.is_email_verified.is_(True))
            .order_by(User.id.desc())
            .limit(200)
            .all()
        )

    return render_template(
        "dashboard/index.html",
        referral_link=referral_link,
        referral_count=referral_count,
        total_earnings=total_earnings,
        referred_users=referred_users,
        active_session=active_session,
        active_users=active_users,
        subscribers=subscribers,
    )