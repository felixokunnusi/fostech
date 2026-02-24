# config.py
import os


def _getenv(key: str, default: str | None = None) -> str | None:
    """Small wrapper to read environment variables."""
    val = os.getenv(key)
    return val if (val is not None and val != "") else default


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _as_float(value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _normalize_db_url(db_url: str) -> str:
    # Render/Heroku sometimes provide "postgres://"; SQLAlchemy wants "postgresql://"
    if db_url.startswith("postgres://"):
        return db_url.replace("postgres://", "postgresql://", 1)
    return db_url


class BaseConfig:
    # -------------------
    # Core / Flask
    # -------------------
    ENV = _getenv("FLASK_ENV", "development")
    DEBUG = _as_bool(_getenv("FLASK_DEBUG"), default=(ENV != "production"))
    TESTING = _as_bool(_getenv("FLASK_TESTING"), default=False)

    SECRET_KEY = _getenv("SECRET_KEY", "dev-secret-key")

    # Cookies / sessions (tighten in ProductionConfig)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = _getenv("SESSION_COOKIE_SAMESITE", "Lax")

    # -------------------
    # Database
    # -------------------
    _db_url = _getenv("DATABASE_URL", "sqlite:///instance/app.db")
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(_db_url)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Optional SQLAlchemy engine options
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    # --------------
    # Quiz Variables
    # --------------
    EXAM_QUESTION_COUNT = 70
    EXAM_DURATION_MINUTES = 40
    TRIAL_QUESTION_COUNT = 10
    GRID_QUESTION_COUNT = 70

    # -------------------
    # Mail / SendGrid
    # -------------------
    MAIL_USERNAME = _getenv("MAIL_USERNAME", "")
    MAIL_DEFAULT_SENDER = _getenv("MAIL_DEFAULT_SENDER", MAIL_USERNAME or "")
    SENDGRID_API_KEY = _getenv("SENDGRID_API_KEY", "")

    SENDGRID_TMPL_ACTIVE_SUBSCRIBERS = _getenv("SENDGRID_TMPL_ACTIVE_SUBSCRIBERS", "")

    SENDGRID_TMPL_ACTIVE_NON_SUBSCRIBERS = _getenv("SENDGRID_TMPL_ACTIVE_NON_SUBSCRIBERS", "")
    APP_NAME = _getenv("APP_NAME", "FOTMASTech CBT App")
    SENDER_NAME = _getenv("SENDER_NAME", "Admin")
    BASE_URL = _getenv("BASE_URL", "https://fotmas.site") # ✅ important for links inside CLI emails
    WEEKLY_EMAIL_LIMIT = _as_int(_getenv("WEEKLY_EMAIL_LIMIT"), default=200)

    # -------------------
    # Referrals / Verification
    # -------------------
    DEFAULT_REFERRAL_CODE = _getenv("DEFAULT_REFERRAL_CODE", "SYSTEM")
    REFERRAL_BONUS = _as_float(_getenv("REFERRAL_BONUS"), default=500.00)
    EMAIL_VERIFICATION_EXPIRY_HOURS = _as_int(_getenv("EMAIL_VERIFICATION_EXPIRY_HOURS"), default=1)

    # -------------------
    # Paystack
    # -------------------
    PAYSTACK_SECRET_KEY = _getenv("PAYSTACK_SECRET_KEY", "")
    PAYSTACK_PUBLIC_KEY = _getenv("PAYSTACK_PUBLIC_KEY", "")

    # -------------------
    # Subscription (kobo)
    # -------------------
    # Default ₦10,000 => 1,000,000 kobo
    SUBSCRIPTION_AMOUNT = _as_int(_getenv("SUBSCRIPTION_AMOUNT"), default=1_000_000)
    MIN_WITHDRAWAL_AMOUNT = _as_int(_getenv("MIN_WITHDRAWAL_AMOUNT"), default=1_000)

    WITHDRAW_FEE_PERCENT = _as_float(_getenv("WITHDRAW_FEE_PERCENT"), default=10.00)
    WITHDRAW_FEE_MIN = _as_float(_getenv("WITHDRAW_FEE_MIN"), default=100.00)
    WITHDRAW_FEE_MAX = None         # optional (e.g. "2000.00")


class DevelopmentConfig(BaseConfig):
    ENV = "development"
    DEBUG = True

    # In dev you can allow missing external services, but your code can still enforce sending.
    # Keeping these here for clarity:
    REQUIRE_EMAIL_CONFIG = _as_bool(_getenv("REQUIRE_EMAIL_CONFIG"), default=False)

class ProductionConfig(BaseConfig):
    ENV = "production"
    DEBUG = False

    # Tighten cookie security for HTTPS deployments
    SESSION_COOKIE_SECURE = True

    