from flask import Flask, redirect, url_for, request
from flask_login import current_user
from .extensions import db, login_manager, migrate, mail


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    # 🔐 Email verification guard
    @app.before_request
    def require_email_verification():
        if current_user.is_authenticated and not current_user.is_email_verified:
            allowed_routes = (
                "auth.confirm_email",
                "auth.resend_confirmation",
                "auth.logout",
                "static",  # VERY important (CSS/JS)
            )

            if request.endpoint not in allowed_routes:
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
