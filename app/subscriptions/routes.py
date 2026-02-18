# app/subscriptions/routes.py
import uuid
import requests
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

from flask import redirect, url_for, current_app, request, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.subscription import Subscription
from app.services.paystack import verify_paystack_payment
from app.services.referral import handle_referral_bonus
from . import subscription_bp

Q = Decimal("0.01")


def _money(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Q, rounding=ROUND_HALF_UP)


@subscription_bp.route("/start")
@login_required
def start_subscription():
    active_sub = (
        Subscription.query
        .filter_by(user_id=current_user.id, is_confirmed=True)
        .order_by(Subscription.expires_at.desc())
        .first()
    )
    if active_sub and active_sub.is_active:
        flash(
            f"You already have an active subscription until {active_sub.expires_at.strftime('%d %b %Y')}.",
            "warning"
        )
        return redirect(url_for("dashboard.index"))

    reference = f"SUB_{uuid.uuid4().hex}"

    kobo = Decimal(str(current_app.config["SUBSCRIPTION_AMOUNT"]))
    naira = (kobo / Decimal("100")).quantize(Q, rounding=ROUND_HALF_UP)

    sub = Subscription(
        user_id=current_user.id,
        amount=naira,
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
        "amount": int(current_app.config["SUBSCRIPTION_AMOUNT"]),  # kobo
        "reference": reference,
        "callback_url": url_for("subscription.verify_subscription", _external=True),
    }

    resp = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json=payload,
        headers=headers,
        timeout=15,
    ).json()

    if not resp.get("status"):
        flash("Unable to start transaction", "danger")
        return redirect(url_for("dashboard.index"))

    return redirect(resp["data"]["authorization_url"])


@subscription_bp.route("/verify")
@login_required
def verify_subscription():
    reference = request.args.get("reference") or ""

    subscription = Subscription.query.filter_by(reference=reference).first()
    if not subscription:
        flash("Invalid payment reference.", "danger")
        return redirect(url_for("dashboard.index"))

    # if webhook already confirmed
    if subscription.is_confirmed:
        flash("Subscription already confirmed.", "info")
        return redirect(url_for("dashboard.index"))

    result = verify_paystack_payment(reference)
    if not result:
        flash("Payment verification failed.", "danger")
        return redirect(url_for("dashboard.index"))

    paid_at_str = result.get("paid_at")
    if paid_at_str:
        subscription.paid_at = datetime.fromisoformat(paid_at_str.replace("Z", "+00:00"))
    else:
        subscription.paid_at = datetime.utcnow()

    subscription.is_confirmed = True
    subscription.set_expiration(days=366)
    db.session.commit()

    # safe: ReferralEarning blocks duplicates
    handle_referral_bonus(subscription)

    flash("Subscription activated successfully!", "success")
    return redirect(url_for("dashboard.index"))
