# app/models/withdrawal.py
from datetime import datetime
from decimal import Decimal
from app.extensions import db


class WithdrawalRequest(db.Model):
    __tablename__ = "withdrawal_requests"

    id = db.Column(db.Integer, primary_key=True)

    # Ensure FK matches your User table name (often "users.id")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    # Gross requested amount (naira)
    amount = db.Column(db.Numeric(12, 2), nullable=False)

    # ✅ Fee + net payout (naira)
    fee = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    net_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    bank_name = db.Column(db.String(120), nullable=True)
    account_name = db.Column(db.String(120), nullable=True)
    account_number = db.Column(db.String(20), nullable=True)
    bank_code = db.Column(db.String(10), nullable=True)

    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    # pending | approved | rejected | processing | paid | failed

    note = db.Column(db.String(255), nullable=True)

    paystack_recipient_code = db.Column(db.String(80), nullable=True)
    paystack_transfer_code = db.Column(db.String(80), nullable=True)
    paystack_reference = db.Column(db.String(80), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    processed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship(
        "User",
        backref=db.backref("withdrawal_requests", lazy="dynamic"),
        foreign_keys=[user_id],
    )

    def __repr__(self) -> str:
        return f"<WithdrawalRequest id={self.id} user_id={self.user_id} amount={self.amount} status={self.status}>"

    @property
    def is_pending(self) -> bool:
        return self.status == "pending"

    @property
    def is_final(self) -> bool:
        return self.status in {"paid", "rejected", "failed"}
