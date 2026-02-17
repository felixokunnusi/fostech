# app/admin/withdrawals.py

from datetime import datetime
from decimal import Decimal

from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models.user import User
from app.models.withdrawal import WithdrawalRequest
from app.utils import admin_required  # ✅ use your shared decorator

from . import admin_bp


@admin_bp.route("/withdrawals", methods=["GET"])
@login_required
@admin_required
def withdrawals():
    withdrawals = (
        WithdrawalRequest.query
        .order_by(WithdrawalRequest.created_at.desc())
        .limit(200)
        .all()
    )
    return render_template("admin/withdrawal.html", withdrawals=withdrawals)


@admin_bp.route("/withdrawals/<int:withdrawal_id>/status", methods=["POST"])
@login_required
@admin_required
def update_withdrawal_status(withdrawal_id: int):
    wr = WithdrawalRequest.query.get_or_404(withdrawal_id)

    new_status = (request.form.get("status") or "").strip().lower()
    note = (request.form.get("note") or "").strip() or None

    allowed = {"pending", "approved", "processing", "paid", "rejected", "failed"}
    if new_status not in allowed:
        flash("Invalid status.", "danger")
        return redirect(url_for("admin.withdrawals"))

    current = (wr.status or "").lower()

    # Final states cannot change
    if current in {"paid", "rejected", "failed"}:
        flash("This withdrawal is already final and cannot be changed.", "warning")
        return redirect(url_for("admin.withdrawals"))

    # Enforce safe transitions
    valid_transitions = {
        "pending": {"approved", "rejected"},
        "approved": {"processing", "rejected", "paid"},
        "processing": {"paid", "failed"},
    }
    if current not in valid_transitions or new_status not in valid_transitions[current]:
        flash(f"Invalid status transition: {current} → {new_status}", "warning")
        return redirect(url_for("admin.withdrawals"))

    try:
        # Reject => refund wallet (because you deduct/reserve at request time)
        if new_status == "rejected":
            with db.session.begin():
                user = (
                    db.session.query(User)
                    .filter(User.id == wr.user_id)
                    .with_for_update()
                    .one()
                )

                user.wallet_balance = (user.wallet_balance or Decimal("0.00")) + (wr.amount or Decimal("0.00"))

                wr.status = "rejected"
                wr.note = note
                wr.processed_at = datetime.utcnow()

            flash("Withdrawal rejected and refunded.", "success")
            return redirect(url_for("admin.withdrawals"))

        # Other updates
        wr.status = new_status
        wr.note = note

        if new_status in {"paid", "failed"}:
            wr.processed_at = datetime.utcnow()
        elif wr.processed_at is None and new_status in {"approved", "processing"}:
            wr.processed_at = datetime.utcnow()
        

        current_app.logger.info(
        f"Admin {current_user.id} set withdrawal {wr.id} → {new_status}"
        )

        db.session.commit()
        flash(f"Withdrawal #{wr.id} updated to {new_status}.", "success")
        return redirect(url_for("admin.withdrawals"))

    except Exception as e:
        db.session.rollback()
        flash(f"Update failed: {e}", "danger")
        return redirect(url_for("admin.withdrawals"))
