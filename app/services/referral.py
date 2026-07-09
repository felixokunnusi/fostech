from decimal import Decimal, ROUND_HALF_UP

from app.extensions import db
from app.models import ReferralEarning, User


MONEY_QUANTIZER = Decimal("0.01")
REFERRAL_PERCENT = Decimal("0.025")  # 2.5%


def _money(value) -> Decimal:
    """
    Convert a value to a Decimal rounded to two decimal places.
    """
    return Decimal(str(value or 0)).quantize(
        MONEY_QUANTIZER,
        rounding=ROUND_HALF_UP,
    )


def handle_referral_bonus(subscription):
    """
    Award a referral bonus when a subscription payment is confirmed.

    The bonus is 2.5% of the actual subscription amount.
    A bonus is awarded only once for each subscription.
    """

    if not subscription or not subscription.id:
        return

    user = db.session.get(User, subscription.user_id)

    if not user:
        return

    # The referred_by field contains the referrer's referral code.
    if not user.referred_by:
        return

    referrer = User.query.filter_by(
        referral_code=user.referred_by
    ).first()

    # Prevent invalid and self-referrals.
    if not referrer or referrer.id == user.id:
        return

    # Prevent duplicate referral earnings for the same subscription.
    already_earned = ReferralEarning.query.filter_by(
        subscription_id=subscription.id
    ).first()

    if already_earned:
        return

    subscription_amount = _money(subscription.amount)

    # Do not create referral earnings for zero or invalid amounts.
    if subscription_amount <= Decimal("0.00"):
        return

    bonus = _money(subscription_amount * REFERRAL_PERCENT)

    if bonus <= Decimal("0.00"):
        return

    earning = ReferralEarning(
        referrer_id=referrer.id,
        referred_user_id=user.id,
        subscription_id=subscription.id,
        amount=bonus,
    )

    current_wallet_balance = _money(referrer.wallet_balance)
    referrer.wallet_balance = _money(current_wallet_balance + bonus)

    db.session.add(earning)
    db.session.commit()