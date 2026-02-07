from flask import render_template, redirect, url_for, request, flash, current_app, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, current_user, login_required
from ..extensions import db
from ..models.user import User
from ..models.subscription import Subscription
from ..utils import generate_code, code_is_expired, generate_referral_code, delete_if_expired_unverified, generate_unique_referral_code
from app.auth.decorators import email_verified_required
from datetime import timedelta, datetime
from . import payments_bp

@payments_bp.route("/webhook/paystack", methods=["POST"])
def paystack_webhook():
    payload = request.get_json()

    if payload["event"] == "charge.success":
        reference = payload["data"]["reference"]

        subscription = Subscription.query.filter_by(
            payment_reference=reference
        ).first()

        if subscription and not subscription.is_confirmed:
            subscription.is_confirmed = True
            db.session.commit()

            # 🎁 REFERRAL BONUS
            from app.services.referral import handle_referral_bonus
            handle_referral_bonus(subscription)

    return "", 200
