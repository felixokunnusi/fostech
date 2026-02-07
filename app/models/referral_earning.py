from datetime import datetime
from app.extensions import db

class ReferralEarning(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    referrer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    referred_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    subscription_id = db.Column(
        db.Integer, db.ForeignKey("subscriptions.id"), nullable=False
    )

    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
     # Relationships
    referrer = db.relationship("User", foreign_keys=[referrer_id], backref="referrals_given")
    referred_user = db.relationship("User", foreign_keys=[referred_user_id], backref="referrals_received")
