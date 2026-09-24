from flask import current_app, abort
import random
import string
import threading
from datetime import datetime, timedelta
import secrets
from functools import wraps 
from flask_login import current_user
from . import db
from app.models import User

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not getattr(current_user, "is_admin", False):
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


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


#--------------------#
# Background Helper
#--------------------#
def run_in_background(func, *args, **kwargs):
    app = current_app._get_current_object()

    def task():
        with app.app_context():
            try:
                func(*args, **kwargs)
            except Exception:
                app.logger.exception("Background task failed")

    threading.Thread(target=task, daemon=True).start()

from datetime import datetime
from zoneinfo import ZoneInfo


NIGERIA_TZ = ZoneInfo("Africa/Lagos")
UTC_TZ = ZoneInfo("UTC")


def nigeria_to_utc(value):
    """
    Convert a naive Nigeria/WAT datetime to a naive UTC datetime.

    Database datetime columns currently store naive datetimes.
    The application treats them as UTC internally.
    """
    if value is None:
        return None

    if value.tzinfo is not None:
        return value.astimezone(UTC_TZ).replace(tzinfo=None)

    nigeria_time = value.replace(tzinfo=NIGERIA_TZ)
    return nigeria_time.astimezone(UTC_TZ).replace(tzinfo=None)


def utc_to_nigeria(value):
    """
    Convert a naive UTC datetime from the database to naive
    Nigeria/WAT datetime for display/editing.
    """
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC_TZ)

    return value.astimezone(NIGERIA_TZ).replace(tzinfo=None)


def now_utc():
    """
    Return the current UTC time as a naive datetime suitable
    for the existing database datetime columns.
    """
    return datetime.now(UTC_TZ).replace(tzinfo=None)


def now_nigeria():
    """
    Return the current Nigeria/WAT time as a naive datetime.
    """
    return datetime.now(NIGERIA_TZ).replace(tzinfo=None)