# app/services/referral.py
from app.models import User, ReferralEarning
from app.extensions import db

REFERRAL_PERCENT = 0.05  # 5%

def handle_referral_bonus(subscription):
    """
    Give referral bonus when a subscription payment is confirmed.
    Bonus is paid ONCE per subscription.
    """

    # The user who paid
    user = User.query.get(subscription.user_id)
    if not user:
        return

    # User was not referred by anyone
    if not user.referred_by:
        return

    # Find the referrer using referral_code
    referrer = User.query.filter_by(referral_code=user.referred_by).first()

    # Safety checks
    if not referrer:
        return
    if referrer.id == user.id:  # self-referral protection
        return

    # Prevent duplicate bonus for same subscription
    already_earned = ReferralEarning.query.filter_by(
        subscription_id=subscription.id
    ).first()

    if already_earned:
        return

    # Calculate bonus
    bonus = round(subscription.amount * REFERRAL_PERCENT, 2)

    # Record earning
    earning = ReferralEarning(
        referrer_id=referrer.id,
        referred_user_id=user.id,
        subscription_id=subscription.id,
        amount=bonus,
    )

    # Update wallet
    referrer.wallet_balance += bonus

    db.session.add(earning)
    db.session.commit()
