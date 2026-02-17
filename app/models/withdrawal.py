# app/models/withdrawal.py
from datetime import datetime
from app.extensions import db


class WithdrawalRequest(db.Model):
    __tablename__ = "withdrawal_requests"

    id = db.Column(db.Integer, primary_key=True)

    # ✅ FK must match your User table name.
    # If User.__tablename__ is "users", keep "users.id".
    # If yours is "user", change to "user.id".
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    # Amount: use Integer if you store money as kobo; Numeric if you store naira decimals.
    # Most Paystack flows are easier with kobo as Integer.
    amount = db.Column(db.Numeric(12, 2), nullable=False)

    # Bank details (for manual payout or Paystack transfer recipient)
    bank_name = db.Column(db.String(120), nullable=True)
    account_name = db.Column(db.String(120), nullable=True)
    account_number = db.Column(db.String(20), nullable=True)

    # Lifecycle
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    # pending | approved | rejected | processing | paid | failed

    note = db.Column(db.String(255), nullable=True)

    # Paystack fields (optional)
    paystack_recipient_code = db.Column(db.String(80), nullable=True)
    paystack_transfer_code = db.Column(db.String(80), nullable=True)
    paystack_reference = db.Column(db.String(80), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    processed_at = db.Column(db.DateTime, nullable=True)

    # Relationship (optional but handy)
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
