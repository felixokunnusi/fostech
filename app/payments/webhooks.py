import hmac
import hashlib
from datetime import datetime

from flask import request, current_app, jsonify, abort

from app.extensions import db
from app.models.subscription import Subscription
from app.models.withdrawal import WithdrawalRequest
from . import payments_bp


def _verify_paystack_signature(raw_body: bytes, signature: str, secret_key: str) -> bool:
    if not signature or not secret_key:
        return False

    computed = hmac.new(
        secret_key.encode("utf-8"),
        raw_body,
        hashlib.sha512,
    ).hexdigest()

    return hmac.compare_digest(computed, signature)


@payments_bp.route("/webhook/paystack", methods=["POST"])
def paystack_webhook():
    secret = current_app.config.get("PAYSTACK_SECRET_KEY") or ""
    signature = request.headers.get("x-paystack-signature", "")
    raw_body = request.get_data(cache=False, as_text=False)

    if not _verify_paystack_signature(raw_body, signature, secret):
        abort(400, description="Invalid Paystack signature")

    payload = request.get_json(silent=True) or {}
    event = (payload.get("event") or "").strip()
    data = payload.get("data") or {}

    # ---------------------------
    # SUBSCRIPTIONS
    # ---------------------------
    if event == "charge.success":
        reference = data.get("reference")
        if not reference:
            return jsonify({"status": "ignored", "reason": "missing_reference"}), 200

        # matches your subscription flow: Subscription.reference
        subscription = Subscription.query.filter_by(reference=reference).first()
        if not subscription:
            return jsonify({"status": "ignored", "reason": "unknown_reference"}), 200

        if subscription.is_confirmed:
            return jsonify({"status": "ignored", "reason": "already_confirmed"}), 200

        subscription.is_confirmed = True
        subscription.paid_at = datetime.utcnow()
        subscription.set_expiration(days=366)
        db.session.commit()

        from app.services.referral import handle_referral_bonus
        handle_referral_bonus(subscription)

        return jsonify({"status": "ok"}), 200

    # ---------------------------
    # WITHDRAWALS (only if you initiate transfers)
    # ---------------------------
    if event.startswith("transfer."):
        reference = data.get("reference")
        transfer_code = data.get("transfer_code")

        if not reference:
            return jsonify({"status": "ignored", "reason": "missing_reference"}), 200

        wr = WithdrawalRequest.query.filter_by(paystack_reference=reference).first()
        if not wr:
            return jsonify({"status": "ignored", "reason": "unknown_reference"}), 200

        if transfer_code and not wr.paystack_transfer_code:
            wr.paystack_transfer_code = transfer_code

        current_status = (wr.status or "").lower()
        if current_status in {"paid", "rejected", "failed"}:
            db.session.commit()
            return jsonify({"status": "ignored", "reason": "already_final"}), 200

        if event == "transfer.success":
            wr.status = "paid"
            wr.processed_at = datetime.utcnow()
            db.session.commit()
            return jsonify({"status": "ok"}), 200

        if event in {"transfer.failed", "transfer.reversed"}:
            reason = data.get("reason") or data.get("message") or event
            wr.status = "failed"
            wr.note = (reason or "")[:250]
            wr.processed_at = datetime.utcnow()
            db.session.commit()
            return jsonify({"status": "ok"}), 200

        db.session.commit()
        return jsonify({"status": "ignored", "reason": "unhandled_transfer_event"}), 200

    return jsonify({"status": "ignored", "reason": "unhandled_event"}), 200
