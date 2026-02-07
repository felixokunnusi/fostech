from flask import render_template, url_for
from flask_login import login_required, current_user
from . import dashboard_bp
from app.auth.decorators import email_verified_required
from app.models import User, ReferralEarning
from sqlalchemy import func
from app.extensions import db

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

    return render_template(
        "dashboard/index.html",
        referral_link=referral_link,
        referral_count=referral_count,
        total_earnings=total_earnings,
        referred_users=referred_users
    )
