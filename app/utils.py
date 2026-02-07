from flask import current_app
import random
import string
from datetime import datetime, timedelta
import secrets
from . import db
from app.models import User

def generate_code():
    return "".join(random.choices(string.digits, k=6))

def code_is_expired(sent_time, minutes=10):
    if not sent_time:
        return True
    delta = datetime.utcnow() - sent_time
    return delta.total_seconds() > minutes * 60


def generate_referral_code():
    while True:
        code = secrets.token_hex(4).upper()
        if not User.query.filter_by(referral_code=code).first():
            return code


def apply_referral_reward(user):
    if not user.referred_by:
        return

    referrer = User.query.filter_by(referral_code=user.referred_by).first()

    if not referrer:
        return

    if referrer.id == user.id:
        return  # hard block self-referral

    referrer.wallet_balance += current_app.config["REFERRAL_BONUS"]
    db.session.add(referrer)


def delete_if_expired_unverified(user):
    if user.is_email_verified:
        return False

    expiry_hours = current_app.config.get("EMAIL_VERIFICATION_EXPIRY_HOURS", 6)
    expiry_time = user.created_at + timedelta(hours=expiry_hours)

    if datetime.utcnow() > expiry_time:
        db.session.delete(user)
        db.session.commit()
        return True

    return False

def generate_unique_referral_code(length=8):
    chars = string.ascii_uppercase + string.digits

    while True:
        code = "".join(random.choices(chars, k=length))
        if not User.query.filter_by(referral_code=code).first():
            return code