from decimal import Decimal, ROUND_HALF_UP
from flask import current_app

Q = Decimal("0.01")

def calc_withdrawal_fee(amount: Decimal) -> tuple[Decimal, Decimal]:
    if amount <= Decimal("0"):
        raise ValueError("Withdrawal amount must be greater than zero.")
    """
    Returns (fee, net_amount)
    Fee rule: max( (pct% of amount), fee_min )
    """
    pct = Decimal(str(current_app.config.get("WITHDRAW_FEE_PERCENT", "10")))
    fee_rate = (pct / Decimal("100"))

    fee = (amount * fee_rate).quantize(Q, rounding=ROUND_HALF_UP)

    fee_min = Decimal(str(current_app.config.get("WITHDRAW_FEE_MIN", "100")))
    fee = max(fee, fee_min)

    fee_max = current_app.config.get("WITHDRAW_FEE_MAX")
    if fee_max is not None:
        fee = min(fee, Decimal(str(fee_max)))

    net = (amount - fee).quantize(Q, rounding=ROUND_HALF_UP)
    return fee, net