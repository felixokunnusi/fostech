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
    """
    Render/Heroku sometimes provide 'postgres://';
    SQLAlchemy prefers 'postgresql://'.
    """
    if db_url.startswith("postgres://"):
        return db_url.replace("postgres://", "postgresql://", 1)
    return db_url


def _get_database_url() -> str:
    """
    Database priority:
    1. NEON_DATABASE_URL - use this when moving to Neon
    2. DATABASE_URL - Render's default database variable
    3. sqlite:///instance/app.db - local development fallback only
    """
    db_url = (
        _getenv("NEON_DATABASE_URL")
        or _getenv("DATABASE_URL")
        or "sqlite:///instance/app.db"
    )
    return _normalize_db_url(db_url)


class BaseConfig:
    # -------------------
    # Core / Flask
    # -------------------
    ENV = _getenv("FLASK_ENV", "development")
    DEBUG = _as_bool(_getenv("FLASK_DEBUG"), default=(ENV != "production"))
    TESTING = _as_bool(_getenv("FLASK_TESTING"), default=False)

    SECRET_KEY = _getenv("SECRET_KEY", "dev-secret-key")

    # Cookies / sessions
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = _getenv("SESSION_COOKIE_SAMESITE", "Lax")

    # -------------------
    # Database
    # -------------------
    SQLALCHEMY_DATABASE_URI = _get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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
    # Mail
    # -------------------
    MAIL_USERNAME = _getenv("MAIL_USERNAME", "")
    MAIL_DEFAULT_SENDER = _getenv("MAIL_DEFAULT_SENDER", MAIL_USERNAME or "")

    EMAIL_PROVIDER = _getenv("EMAIL_PROVIDER", "brevo")
    EMAIL_PROVIDER_CHAIN = _getenv("EMAIL_PROVIDER_CHAIN", "")

    # --- Brevo SMTP ---
    BREVO_SMTP_HOST = _getenv("BREVO_SMTP_HOST", "smtp-relay.brevo.com")
    BREVO_SMTP_PORT = _as_int(_getenv("BREVO_SMTP_PORT", "587"), default=587)
    BREVO_SMTP_USERNAME = _getenv("BREVO_SMTP_USERNAME", "")
    BREVO_SMTP_PASSWORD = _getenv("BREVO_SMTP_PASSWORD", "")

    # --- Zoho SMTP ---
    ZOHO_SMTP_HOST = _getenv("ZOHO_SMTP_HOST", "smtppro.zoho.com")
    ZOHO_SMTP_PORT = _as_int(_getenv("ZOHO_SMTP_PORT", "587"), default=587)
    ZOHO_SMTP_USERNAME = _getenv("ZOHO_SMTP_USERNAME", "")
    ZOHO_SMTP_PASSWORD = _getenv("ZOHO_SMTP_PASSWORD", "")

    # --- MailerSend SMTP ---
    MAILERSEND_SMTP_HOST = _getenv("MAILERSEND_SMTP_HOST", "smtp.mailersend.net")
    MAILERSEND_SMTP_PORT = _as_int(_getenv("MAILERSEND_SMTP_PORT", "587"), default=587)
    MAILERSEND_SMTP_USERNAME = _getenv("MAILERSEND_SMTP_USERNAME", "")
    MAILERSEND_SMTP_PASSWORD = _getenv("MAILERSEND_SMTP_PASSWORD", "")

    # -------------------
    # App / Campaign settings
    # -------------------
    APP_NAME = _getenv("APP_NAME", "FOTMASTech CBT App")
    SENDER_NAME = _getenv("SENDER_NAME", "Admin")
    BASE_URL = _getenv("BASE_URL", "https://fotmas.site")
    WEEKLY_EMAIL_LIMIT = _as_int(_getenv("WEEKLY_EMAIL_LIMIT"), default=200)

    # -------------------
    # Referrals / Verification
    # -------------------
    DEFAULT_REFERRAL_CODE = _getenv("DEFAULT_REFERRAL_CODE", "SYSTEM")
    REFERRAL_BONUS = _as_float(_getenv("REFERRAL_BONUS"), default=500.00)
    EMAIL_VERIFICATION_EXPIRY_HOURS = _as_int(
        _getenv("EMAIL_VERIFICATION_EXPIRY_HOURS"),
        default=1
    )

    # -------------------
    # Paystack
    # -------------------
    PAYSTACK_SECRET_KEY = _getenv("PAYSTACK_SECRET_KEY", "")
    PAYSTACK_PUBLIC_KEY = _getenv("PAYSTACK_PUBLIC_KEY", "")

    # -------------------
    # Subscription / Withdrawal
    # -------------------
    # Default ₦10,000 => 1,000,000 kobo
    SUBSCRIPTION_AMOUNT = _as_int(_getenv("SUBSCRIPTION_AMOUNT"), default=1_000_000)
    MIN_WITHDRAWAL_AMOUNT = _as_int(_getenv("MIN_WITHDRAWAL_AMOUNT"), default=1_000)

    WITHDRAW_FEE_PERCENT = _as_float(_getenv("WITHDRAW_FEE_PERCENT"), default=10.00)
    WITHDRAW_FEE_MIN = _as_float(_getenv("WITHDRAW_FEE_MIN"), default=100.00)

    _withdraw_fee_max = _getenv("WITHDRAW_FEE_MAX", "")
    WITHDRAW_FEE_MAX = (
        _as_float(_withdraw_fee_max, default=0.0)
        if _withdraw_fee_max
        else None
    )


class DevelopmentConfig(BaseConfig):
    ENV = "development"
    DEBUG = True

    REQUIRE_EMAIL_CONFIG = _as_bool(
        _getenv("REQUIRE_EMAIL_CONFIG"),
        default=False
    )


class ProductionConfig(BaseConfig):
    ENV = "production"
    DEBUG = False

    # HTTPS deployment
    SESSION_COOKIE_SECURE = True

    REQUIRE_EMAIL_CONFIG = _as_bool(
        _getenv("REQUIRE_EMAIL_CONFIG"),
        default=True
    )


class TestingConfig(BaseConfig):
    ENV = "testing"
    DEBUG = False
    TESTING = True

    SQLALCHEMY_DATABASE_URI = _normalize_db_url(
        _getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    )


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}