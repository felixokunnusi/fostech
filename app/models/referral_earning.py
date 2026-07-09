from datetime import datetime
from decimal import Decimal

from app.extensions import db


class ReferralEarning(db.Model):
    __tablename__ = "referral_earning"

    id = db.Column(db.Integer, primary_key=True)

    referrer_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True,
    )

    referred_user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True,
    )

    subscription_id = db.Column(
        db.Integer,
        db.ForeignKey("subscriptions.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    amount = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    referrer = db.relationship(
        "User",
        foreign_keys=[referrer_id],
        backref="referrals_given",
    )

    referred_user = db.relationship(
        "User",
        foreign_keys=[referred_user_id],
        backref="referrals_received",
    )