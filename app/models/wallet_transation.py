from app.extensions import db
from flask_login import UserMixin
from datetime import datetime, timedelta
import uuid

class WalletTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(50))  # 'referral_bonus', 'subscription_credit', etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
