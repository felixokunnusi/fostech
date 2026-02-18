# app/services/referral.py
from decimal import Decimal, ROUND_HALF_UP
from app.models import User, ReferralEarning
from app.extensions import db

Q = Decimal("0.01")
REFERRAL_PERCENT = Decimal("0.05")  # 5%

def _money(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Q, rounding=ROUND_HALF_UP)

def handle_referral_bonus(subscription):
    """
    Give referral bonus when a subscription payment is confirmed.
    Bonus is paid ONCE per subscription (enforced by ReferralEarning check).
    """

    user = db.session.get(User, subscription.user_id)
    if not user:
        return

    if not user.referred_by:
        return

    referrer = User.query.filter_by(referral_code=user.referred_by).first()
    if not referrer or referrer.id == user.id:
        return

    already_earned = ReferralEarning.query.filter_by(subscription_id=subscription.id).first()
    if already_earned:
        return

    amount = _money(subscription.amount)
    bonus = (amount * REFERRAL_PERCENT).quantize(Q, rounding=ROUND_HALF_UP)

    earning = ReferralEarning(
        referrer_id=referrer.id,
        referred_user_id=user.id,
        subscription_id=subscription.id,
        amount=bonus,
    )

    if referrer.wallet_balance is None:
        referrer.wallet_balance = Decimal("0.00")

    referrer.wallet_balance = _money(referrer.wallet_balance) + bonus

    db.session.add(earning)
    db.session.commit()
