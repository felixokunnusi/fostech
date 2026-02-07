# Referral Stats UI (Flask)
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import ReferralEarning, User
from app.extensions import db
from sqlalchemy import func
from . import referral_bp

@referral_bp.route("/stats")
@login_required
def referral_stats():
    total_earnings = db.session.query(
        func.coalesce(func.sum(ReferralEarning.amount), 0)
    ).filter(
        ReferralEarning.referrer_id == current_user.id
    ).scalar()

    total_referrals = ReferralEarning.query.filter_by(
        referrer_id=current_user.id
    ).count()

    recent_earnings = ReferralEarning.query.filter_by(
        referrer_id=current_user.id
    ).order_by(ReferralEarning.created_at.desc())\
     .limit(10).all()

    return render_template(
        "referrals/stats.html",
        total_earnings=total_earnings,
        total_referrals=total_referrals,
        recent_earnings=recent_earnings,
        wallet_balance=current_user.wallet_balance,
        referral_code=current_user.referral_code,
    )
