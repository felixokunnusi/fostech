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
    referral_link = url_for(
        "auth.register",
        ref=current_user.referral_code,
        _external=True
    )

    referral_count = User.query.filter_by(
        referred_by=current_user.referral_code
    ).count()

    total_earnings = (
        db.session.query(func.coalesce(func.sum(ReferralEarning.amount), 0))
        .filter(ReferralEarning.referrer_id == current_user.id)
        .scalar()
    )

    referred_users = (
        db.session.query(
            User.username,
            User.email,
            func.coalesce(func.sum(ReferralEarning.amount), 0).label("earned")
        )
        .outerjoin(
            ReferralEarning,
            ReferralEarning.referred_user_id == User.id
        )
        .filter(User.referred_by == current_user.referral_code)
        .group_by(User.id)
        .all()
    )

    # ✅ Active (unfinished) quiz session
    active_session = (
        QuizSession.query
        .filter_by(user_id=current_user.id, is_submitted=False)
        .order_by(QuizSession.started_at.desc())
        .first()
    )

    # ✅ If active exam expired → auto-submit it
    if (
        active_session
        and active_session.mode == "exam"
        and active_session.expires_at
        and datetime.utcnow() > active_session.expires_at
    ):
        active_session.is_submitted = True
        active_session.completed_at = datetime.utcnow()
        db.session.commit()
        active_session = None

    # ✅ Admin-only: confirmed subscribers list
    from app.models import Subscription  # ✅ local import avoids circular import
    subscribers = []
    if getattr(current_user, "is_admin", False):
        subscribers = (
            db.session.query(User, Subscription)
            .join(Subscription, Subscription.user_id == User.id)
            .filter(Subscription.is_confirmed.is_(True))
            .order_by(Subscription.id.desc())
            .all()
        )

    return render_template(
        "dashboard/index.html",
        referral_link=referral_link,
        referral_count=referral_count,
        total_earnings=total_earnings,
        referred_users=referred_users,
        active_session=active_session,
        subscribers=subscribers,  # ✅ add this
    )