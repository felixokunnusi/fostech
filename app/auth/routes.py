from flask import render_template, redirect, url_for, request, flash, current_app, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, current_user, login_required
from ..extensions import db
from ..models.user import User
from . import auth_bp
from .forms import RegisterForm, LoginForm, ConfirmEmailForm
from .. utils import generate_code, code_is_expired, generate_referral_code, delete_if_expired_unverified, generate_unique_referral_code
from .email import send_confirmation_email, send_password_reset_email
from app.auth.decorators import email_verified_required
from datetime import timedelta, datetime
import random
from .utils import generate_reset_token
import secrets


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = RegisterForm()

    # Referral via link only (?ref=CODE)
    referral_code = request.args.get("ref") or session.get("ref")

    if not referral_code:
        referral_code = current_app.config.get("DEFAULT_REFERRAL_CODE")

    referrer = User.query.filter_by(referral_code=referral_code).first()
    if not referrer:
        referral_code = current_app.config.get("DEFAULT_REFERRAL_CODE")

    if form.validate_on_submit():

        # Prevent duplicate email
        if User.query.filter_by(email=form.email.data).first():
            flash("Email already registered.", "danger")
            return render_template("auth/register.html", form=form)

        # Prevent duplicate username
        if User.query.filter_by(username=form.username.data).first():
            flash("Username already taken.", "danger")
            return render_template("auth/register.html", form=form)

        # 🔐 Generate 6-digit email code
        email_code = str(random.randint(100000, 999999))

        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            is_email_verified=False,
            email_confirm_code=email_code,
            email_confirm_expires=datetime.utcnow() + timedelta(minutes=10),
            email_code_sent_at=datetime.utcnow(),
            last_confirmation_sent=datetime.utcnow(),
            referred_by=referral_code
        )

        db.session.add(user)
        db.session.commit()

        session.pop("ref", None)  # ✅ prevent referral carrying over to future signups

        # Send verification email
        send_confirmation_email(user)

        # Store email for verification step
        session["verify_email"] = user.email

        flash("Enter the 6-digit code sent to your email.", "info")
        return redirect(url_for("auth.confirm_email"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user and delete_if_expired_unverified(user):
            flash("Your account expired. Please register again.", "danger")
            return redirect(url_for("auth.register"))

        # Invalid credentials
        if not user or not user.check_password(form.password.data):
            flash("Invalid email or password", "danger")
            return render_template("auth/login.html", form=form)

        # 🔐 Email NOT verified → force confirmation flow
        if not user.is_email_verified:
            session["verify_email"] = user.email
            flash("Please confirm your email to continue.", "warning")
            return redirect(url_for("auth.confirm_email"))

        # ✅ Single session per user 
        token = secrets.token_urlsafe(32)
        user.current_session_token = token
        db.session.commit()
        session["session_token"] = token

         # ✅ Verified → login 
        login_user(user)
        return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html", form=form)

@auth_bp.route('/logout')
def logout():
    if current_user.is_authenticated:
        current_user.current_session_token = None
        db.session.commit()
    logout_user()
    return redirect(url_for('auth.login'))


#Confirmation route
@auth_bp.route("/confirm-email", methods=["GET", "POST"])
def confirm_email():
    email = session.get("verify_email")
    if not email:
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Account not found.", "danger")
        return redirect(url_for("auth.register"))

    if delete_if_expired_unverified(user):
        session.pop("verify_email", None)
        flash("Verification time expired. Please register again.", "danger")
        return redirect(url_for("auth.register"))
    form = ConfirmEmailForm()

    if form.validate_on_submit():
        if (
            user.email_confirm_code != form.code.data
            or user.email_confirm_expires < datetime.utcnow()
        ):
            flash("Invalid or expired code.", "danger")
            return redirect(url_for("auth.confirm_email"))

        # ✅ Mark email verified
        user.is_email_verified = True
        user.email_confirm_code = None
        user.email_confirm_expires = None

        # 🎁 Generate referral code HERE
        if not user.referral_code:
            user.referral_code = generate_unique_referral_code()
            

        db.session.commit()

        session.pop("verify_email", None)

        flash("Email verified successfully! You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/confirm_email.html", form=form)


# Resend Code
# Resend Code
@auth_bp.route("/resend-confirmation")
def resend_confirmation():
    email = session.get("verify_email")
    user = User.query.filter_by(email=email).first()

    if not user or user.is_email_verified:
        return redirect(url_for("auth.login"))

    # ⏱ Cooldown (e.g. 60 seconds)
    if user.last_confirmation_sent and \
       datetime.utcnow() - user.last_confirmation_sent < timedelta(seconds=60):
        flash("Please wait before resending.", "warning")
        return redirect(url_for("auth.confirm_email"))

    if delete_if_expired_unverified(user):
        flash("Account expired. Please register again.", "danger")
        return redirect(url_for("auth.register"))

    # Generate new code
    user.email_confirm_code = str(random.randint(100000, 999999))
    user.email_confirm_expires = datetime.utcnow() + timedelta(minutes=10)
    user.last_confirmation_sent = datetime.utcnow()

    db.session.commit()

    # 🔥 SAFE email send
    try:
        send_confirmation_email(user)

    except RuntimeError as e:
        flash(str(e), "danger")
        return redirect(url_for("auth.confirm_email"))

    except Exception:
        flash("Unable to send email right now. Please try again later.", "danger")
        return redirect(url_for("auth.confirm_email"))

    flash("New confirmation code sent.", "success")
    return redirect(url_for("auth.confirm_email"))

# Password reset
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("If that email exists, a reset link has been sent.", "info")
            return redirect(url_for("auth.login"))

        user.reset_token = generate_reset_token()
        user.reset_token_expires = datetime.utcnow() + timedelta(minutes=30)
        db.session.commit()

        send_password_reset_email(user)
        flash("Password reset link sent. Check your email.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")

# Password reset token
@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()

    if not user or user.reset_token_expires < datetime.utcnow():
        flash("Reset link is invalid or expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password")
        confirm = request.form.get("confirm_password")

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(request.url)

        user.set_password(password)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()

        flash("Password reset successful. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html")

