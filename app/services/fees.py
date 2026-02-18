from decimal import Decimal, ROUND_HALF_UP
from flask import current_app

Q = Decimal("0.01")

def calc_withdrawal_fee(amount: Decimal) -> tuple[Decimal, Decimal]:
    """
    Returns (fee, net_amount)
    """
    pct = Decimal(str(current_app.config.get("WITHDRAW_FEE_PERCENT", "0.10")))
    fee = (amount * pct).quantize(Q, rounding=ROUND_HALF_UP)

    fee_min = Decimal(str(current_app.config.get("WITHDRAW_FEE_MIN", "0.00")))
    fee = max(fee, fee_min)

    fee_max = current_app.config.get("WITHDRAW_FEE_MAX")
    if fee_max is not None:
        fee = min(fee, Decimal(str(fee_max)))

    net = (amount - fee).quantize(Q, rounding=ROUND_HALF_UP)
    return fee, net
