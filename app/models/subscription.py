from app.extensions import db
from flask_login import UserMixin
from datetime import datetime, timedelta
import uuid

class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)

    # 🔗 Relationships done in user model
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # 💰 Payment info
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="NGN")

    payment_provider = db.Column(db.String(20))  # paystack | flutterwave
    payment_reference = db.Column(db.String(120), unique=True, index=True)

    # ✅ Confirmation
    is_confirmed = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime)

    # 🕒 Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)  # new
    # for paystack webhook
    reference = db.Column(db.String(100), unique=True, nullable=False)

    def confirm_payment(self):
        self.is_confirmed = True
        self.paid_at = datetime.utcnow()
    def set_expiration(self, days=366):
        """Set expiration date based on paid_at."""
        if not self.paid_at:
            self.paid_at = datetime.utcnow()
        self.expires_at = self.paid_at + timedelta(days=days) # 1 year

    # Restrict active sub to 1
    @property
    def is_active(self):
        return (
            self.is_confirmed
            and self.expires_at is not None
            and self.expires_at > datetime.utcnow()
        )