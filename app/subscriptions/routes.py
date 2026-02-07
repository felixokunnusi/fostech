import uuid
from flask import Blueprint, redirect, url_for, current_app, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app.extensions import db
from app.models.subscription import Subscription
from app.services.paystack import verify_paystack_payment
from app.services.referral import handle_referral_bonus
from . import subscription_bp
import uuid
import requests
import hmac, hashlib

@subscription_bp.route("/start")
@login_required
def start_subscription():
    reference = f"SUB_{uuid.uuid4().hex}"

    sub = Subscription(
        user_id=current_user.id,
        amount=current_app.config["SUBSCRIPTION_AMOUNT"] / 100, # convert kobo → naira
        reference=reference,
        is_confirmed=False
    )
    db.session.add(sub)
    db.session.commit()

    headers = {
        "Authorization": f"Bearer {current_app.config['PAYSTACK_SECRET_KEY']}",
        "Content-Type": "application/json",
    }

    payload = {
        "email": current_user.email,
        "amount": current_app.config["SUBSCRIPTION_AMOUNT"],  # kobo
        "reference": reference,
        "callback_url": url_for("subscription.verify_subscription", _external=True),
    }

    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json=payload,
        headers=headers,
        timeout=15,
    ).json()

    if not response.get("status"):
        flash("Unable to start transaction", "danger")
        return redirect(url_for("dashboard.index"))

    return redirect(response["data"]["authorization_url"])


@subscription_bp.route("/verify")
@login_required
def verify_subscription():
    reference = request.args.get("reference")

    subscription = Subscription.query.filter_by(reference=reference).first()
    if not subscription:
        flash("Invalid payment reference.", "danger")
        return redirect(url_for("dashboard.index"))

    result = verify_paystack_payment(reference)
    if not result:
        flash("Payment verification failed.", "danger")
        return redirect(url_for("dashboard.index"))

    if subscription.is_confirmed:
        flash("Payment already confirmed.", "info")
        return redirect(url_for("dashboard.index"))

    # ✅ Convert Paystack datetime string → Python datetime
    paid_at_str = result.get("paid_at")
    if paid_at_str:
        subscription.paid_at = datetime.fromisoformat(
            paid_at_str.replace("Z", "+00:00")
        )
    else:
        subscription.paid_at = datetime.utcnow()

    subscription.is_confirmed = True
    subscription.set_expiration(days=366)  # 366-day subscription (1 year)
    db.session.commit()

    # 🎁 Referral reward
    handle_referral_bonus(subscription)

    flash("Subscription activated successfully!", "success")
    return redirect(url_for("dashboard.index"))

# app/subscriptions/routes.py
@subscription_bp.route("/paystack/webhook", methods=["POST"])
def paystack_webhook():
    payload = request.get_data()
    signature = request.headers.get("x-paystack-signature")
    
    # Verify signature
    secret = current_app.config["PAYSTACK_SECRET_KEY"].encode()
    hash = hmac.new(secret, payload, hashlib.sha512).hexdigest()
    if hash != signature:
        return jsonify({"status": "error", "message": "Invalid signature"}), 400

    data = request.get_json()
    event = data.get("event")

    if event == "charge.success":
        ref = data["data"]["reference"]
        subscription = Subscription.query.filter_by(reference=ref).first()
        if subscription and not subscription.is_confirmed:
            subscription.is_confirmed = True
            subscription.paid_at = datetime.utcnow()
            subscription.set_expiration(days=30)
            db.session.commit()
            handle_referral_bonus(subscription)

    return jsonify({"status": "success"})
