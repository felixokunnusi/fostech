
from flask import current_app, abort
import random
import string
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import secrets
from functools import wraps

from flask_login import current_user
from sqlalchemy import (
     or_,
    inspect as sqlalchemy_inspect,
    MetaData,
    Table,
    select,
    exists,
    delete,
)

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

    referrer = User.query.filter_by(
        referral_code=user.referred_by
    ).first()

    if not referrer:
        return

    if referrer.id == user.id:
        return

    referrer.wallet_balance += current_app.config["REFERRAL_BONUS"]
    db.session.add(referrer)


def is_expired_unverified_account(user, now=None):
    """
    Check whether an account has remained unverified
    for the configured registration expiry period.

    Verified accounts and accounts without created_at
    are never considered expired by this function.
    """
    if user is None or user.is_email_verified:
        return False

    if user.created_at is None:
        return False

    expiry_hours = current_app.config.get(
        "EMAIL_VERIFICATION_EXPIRY_HOURS",
        6
    )

    if now is None:
        now = datetime.utcnow()

    expiry_time = user.created_at + timedelta(
        hours=expiry_hours
    )

    return now >= expiry_time



def _get_user_deletion_safety_conditions():
    """
    Inspect the actual database foreign keys and return SQL
    conditions ensuring that a user has no dependent records.

    This uses database inspection rather than relying solely
    on imported SQLAlchemy model classes.

    If inspection fails, deletion must fail safely.
    """
    inspector = sqlalchemy_inspect(db.engine)
    metadata = MetaData()
    conditions = []

    for table_name in inspector.get_table_names():

        if table_name == User.__tablename__:
            continue

        foreign_keys = inspector.get_foreign_keys(table_name)

        for foreign_key in foreign_keys:

            if foreign_key.get("referred_table") != User.__tablename__:
                continue

            local_columns = foreign_key.get("constrained_columns") or []
            remote_columns = foreign_key.get("referred_columns") or []

            if not local_columns or len(local_columns) != len(remote_columns):
                raise RuntimeError(
                    f"Could not safely inspect foreign key in {table_name}."
                )

            if table_name in metadata.tables:
                dependent_table = metadata.tables[table_name]
            else:
                dependent_table = Table(
                    table_name,
                    metadata,
                    autoload_with=db.engine
                )

            relationship_conditions = []

            for local_column, remote_column in zip(
                local_columns,
                remote_columns
            ):
                relationship_conditions.append(
                    dependent_table.c[local_column]
                    == User.__table__.c[remote_column]
                )

            dependent_record_exists = exists(
                select(1)
                .select_from(dependent_table)
                .where(*relationship_conditions)
            )

            conditions.append(~dependent_record_exists)

    return conditions


def delete_if_expired_unverified(user):
    """
    Delete one expired, unverified account only if it has
    no dependent records.

    Returns:
        True  - account was successfully deleted.
        False - account is not expired or has dependent records.

    Raises an exception if database deletion fails.
    """
    if not is_expired_unverified_account(user):
        return False

    expiry_hours = current_app.config.get(
        "EMAIL_VERIFICATION_EXPIRY_HOURS",
        6
    )

    cutoff_time = datetime.utcnow() - timedelta(
        hours=expiry_hours
    )

    try:
        safety_conditions = _get_user_deletion_safety_conditions()

        result = db.session.execute(
            delete(User).where(
                User.id == user.id,
                or_(
                    User.is_email_verified.is_(False),
                    User.is_email_verified.is_(None)
                ),
                User.created_at.isnot(None),
                User.created_at <= cutoff_time,
                *safety_conditions
            ).execution_options(synchronize_session=False)
        )

        deleted = result.rowcount > 0

        db.session.commit()

        return deleted

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Failed to delete expired unverified account."
        )

        raise


def cleanup_expired_unverified_users():
    """
    Efficiently delete expired, unverified accounts that have
    no dependent database records.

    Uses a direct database DELETE statement rather than ORM
    session.delete(), avoiding relationship-loading overhead.

    Verified accounts and accounts with missing created_at
    are never deleted.

    All eligible deletions are performed in one transaction.
    """
    expiry_hours = current_app.config.get(
        "EMAIL_VERIFICATION_EXPIRY_HOURS",
        6
    )

    cutoff_time = datetime.utcnow() - timedelta(
        hours=expiry_hours
    )

    try:
        safety_conditions = _get_user_deletion_safety_conditions()

        result = db.session.execute(
            delete(User).where(
                or_(
                    User.is_email_verified.is_(False),
                    User.is_email_verified.is_(None)
                ),
                User.created_at.isnot(None),
                User.created_at <= cutoff_time,
                *safety_conditions
            ).execution_options(synchronize_session=False)
        )

        deleted_count = result.rowcount or 0

        db.session.commit()

        current_app.logger.info(
            "Expired registration cleanup completed. "
            "Deleted %s accounts.",
            deleted_count
        )

        return deleted_count

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Failed to clean up expired unverified accounts."
        )

        raise


def generate_unique_referral_code(length=8):
    chars = string.ascii_uppercase + string.digits

    while True:
        code = "".join(random.choices(chars, k=length))

        if not User.query.filter_by(referral_code=code).first():
            return code


# -------------------- #
# Background Helper
# -------------------- #

def run_in_background(func, *args, **kwargs):
    app = current_app._get_current_object()

    def task():
        with app.app_context():
            try:
                func(*args, **kwargs)
            except Exception:
                app.logger.exception("Background task failed")

    threading.Thread(target=task, daemon=True).start()


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

    return nigeria_time.astimezone(
        UTC_TZ
    ).replace(tzinfo=None)


def utc_to_nigeria(value):
    """
    Convert a naive UTC datetime from the database to naive
    Nigeria/WAT datetime for display/editing.
    """
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC_TZ)

    return value.astimezone(
        NIGERIA_TZ
    ).replace(tzinfo=None)


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
