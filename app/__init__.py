import os
from flask import Flask, redirect, url_for, request
from flask_login import current_user

from .extensions import db, login_manager, migrate, mail



def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # ensure instance folder exists (Flask-managed)
    os.makedirs(app.instance_path, exist_ok=True)

    # Load config by environment
    env = os.getenv("FLASK_ENV", "development").lower()
    cfg = "config.ProductionConfig" if env == "production" else "config.DevelopmentConfig"
    app.config.from_object(cfg)
    is_prod = (env == "production")
    if is_prod:
        missing = []
        if not os.getenv("SECRET_KEY"):
            missing.append("SECRET_KEY")
        if not os.getenv("DATABASE_URL"):
            missing.append("DATABASE_URL")
        if not os.getenv("SENDGRID_API_KEY") or not os.getenv("MAIL_DEFAULT_SENDER"):
            missing.append("SENDGRID_API_KEY/MAIL_DEFAULT_SENDER")
        if not os.getenv("PAYSTACK_SECRET_KEY") or not os.getenv("PAYSTACK_PUBLIC_KEY"):
            missing.append("PAYSTACK_SECRET_KEY/PAYSTACK_PUBLIC_KEY")

        if missing:
            raise RuntimeError("Missing required production settings: " + ", ".join(missing))


    # If using sqlite and path is relative, force it into instance_path (Windows-safe)
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("sqlite:///") and not uri.startswith("sqlite:////"):
        db_file = os.path.join(app.instance_path, "app.db")
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_file.replace("\\", "/")

    # Init extensions
    db.init_app(app)
    import sqlite3
    from decimal import Decimal
    sqlite3.register_adapter(Decimal, lambda d: str(d))
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    # 🔐 Email verification guard (safe + predictable)
    @app.before_request
    def require_email_verification():
        if not current_user.is_authenticated:
            return

        # Some requests don't have endpoints (rare, but happens)
        if request.endpoint is None:
            return

        # Always allow static assets
        if request.endpoint.startswith("static"):
            return

        allowed_routes = {
            "auth.confirm_email",
            "auth.resend_confirmation",
            "auth.logout",
            "auth.login",
            "auth.register",
        }

        if request.endpoint in allowed_routes:
            return

        # Avoid crashes if attribute missing (old sessions / stale rows)
        if not getattr(current_user, "is_email_verified", False):
            return redirect(url_for("auth.confirm_email"))

    # Blueprints
    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.dashboard.routes import dashboard_bp
    from app.subscriptions.routes import subscription_bp
    from app.referrals.routes import referral_bp
    from app.quiz import quiz_bp
    from app.admin import admin_bp
    
   

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(subscription_bp)
    app.register_blueprint(referral_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(admin_bp)

    return app
