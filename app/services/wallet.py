from decimal import Decimal
from sqlalchemy import func
from app.extensions import db
from app.models.withdrawal import WithdrawalRequest


def get_withdrawable_balance(user_id: int, wallet_balance):
    pending_sum = db.session.query(
        func.coalesce(func.sum(WithdrawalRequest.amount), 0)
    ).filter(
        WithdrawalRequest.user_id == user_id,
        WithdrawalRequest.status.in_(["pending", "approved", "processing"])
    ).scalar()

    wallet = Decimal(str(wallet_balance or 0))
    pending = Decimal(str(pending_sum or 0))

    return wallet - pending
