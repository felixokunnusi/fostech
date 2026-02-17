from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from flask_login import UserMixin
from datetime import datetime
import uuid
from sqlalchemy import Numeric, CheckConstraint
from decimal import Decimal


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_email_verified = db.Column(db.Boolean, default=False)
    email_confirm_code = db.Column(db.String(6), nullable=True)
    referral_code = db.Column(db.String(10), unique=True)
    referred_by = db.Column(db.String(10))
    # wallet_balance = db.Column(db.Float, default=0.0)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    email_code_sent_at = db.Column(db.DateTime)
    email_confirm_expires = db.Column(db.DateTime)
    last_confirmation_sent = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reset_token = db.Column(db.String(255), index=True)
    reset_token_expires = db.Column(db.DateTime)
    wallet_balance = db.Column(Numeric(12,2), default=Decimal("0.00"))

    __table_args__ = (
    CheckConstraint("wallet_balance >= 0", name="wallet_balance_non_negative"),
    )

    # ✅ ADD THIS
    subscriptions = db.relationship(
        "Subscription",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )


    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
