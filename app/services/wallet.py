# app/referrals/utils.py (or app/services/wallet.py)
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

    return float(wallet_balance) - float(pending_sum)
