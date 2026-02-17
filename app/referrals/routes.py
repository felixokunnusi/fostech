# Referral Stats UI (Flask)
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.models import ReferralEarning, User  # adjust import paths if different
from app.extensions import db
from sqlalchemy import func
from . import referral_bp
# app/referrals/routes.py
from app.models.withdrawal import WithdrawalRequest
from app.services.wallet import get_withdrawable_balance
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


@referral_bp.route("/stats")
@login_required
def referral_stats():
    total_earnings = db.session.query(
        func.coalesce(func.sum(ReferralEarning.amount), 0)
    ).filter(
        ReferralEarning.referrer_id == current_user.id
    ).scalar()

    total_referrals = ReferralEarning.query.filter_by(
        referrer_id=current_user.id
    ).count()

    recent_earnings = ReferralEarning.query.filter_by(
        referrer_id=current_user.id
    ).order_by(ReferralEarning.created_at.desc())\
     .limit(10).all()

    return render_template(
        "referrals/stats.html",
        total_earnings=total_earnings,
        total_referrals=total_referrals,
        recent_earnings=recent_earnings,
        wallet_balance=current_user.wallet_balance,
        referral_code=current_user.referral_code,
    )


MIN_WITHDRAWAL = Decimal("1000.00")  # ₦1,000


def _money(v) -> Decimal:
    """Convert anything to a 2dp Decimal safely."""
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@referral_bp.route("/withdraw", methods=["GET", "POST"])
@login_required
def request_withdrawal():
    # ✅ pull minimum from config (expects NAIRA Decimal/number like 1000 or 1000.00)
    MIN_WITHDRAWAL = _money(current_app.config.get("MIN_WITHDRAWAL_AMOUNT", ""))

    # compute withdrawable (wallet - pending)
    withdrawable = _money(get_withdrawable_balance(current_user.id, current_user.wallet_balance))

    if request.method == "POST":
        raw_amount = (request.form.get("amount") or "").strip()
        bank_name = (request.form.get("bank_name") or "").strip()
        account_name = (request.form.get("account_name") or "").strip()
        account_number = (request.form.get("account_number") or "").strip()

        # Validate amount
        try:
            amount = _money(raw_amount)
        except (InvalidOperation, TypeError):
            flash("Enter a valid withdrawal amount.", "danger")
            return redirect(url_for("referrals.request_withdrawal"))

        if amount <= Decimal("0.00"):
            flash("Amount must be greater than ₦0.", "danger")
            return redirect(url_for("referrals.request_withdrawal"))

        # ✅ Minimum withdrawal enforcement
        if amount < MIN_WITHDRAWAL:
            flash(f"Minimum withdrawal is ₦{MIN_WITHDRAWAL:,.2f}.", "warning")
            return redirect(url_for("referrals.request_withdrawal"))

        # Optional: validate bank fields
        if not (bank_name and account_name and account_number):
            flash("Please fill in your bank details.", "danger")
            return redirect(url_for("referrals.request_withdrawal"))

        # --- ATOMIC SECTION ---
        try:
            # Lock the user row so two withdrawals can't pass at once
            user_row = (
                db.session.query(User)
                .filter(User.id == current_user.id)
                .with_for_update()
                .one()
            )

            # recompute inside lock
            withdrawable_locked = _money(
                get_withdrawable_balance(user_row.id, user_row.wallet_balance)
            )

            if amount > withdrawable_locked:
                flash(
                    f"Insufficient withdrawable balance. Available: ₦{withdrawable_locked:,.2f}",
                    "danger",
                )
                db.session.rollback()
                return redirect(url_for("referrals.request_withdrawal"))

            # Create request
            wr = WithdrawalRequest(
                user_id=user_row.id,
                amount=amount,
                bank_name=bank_name,
                account_name=account_name,
                account_number=account_number,
                status="pending",
            )

            # Reserve funds immediately
            user_row.wallet_balance = _money(user_row.wallet_balance) - amount

            db.session.add(wr)
            db.session.commit()

        except Exception:
            db.session.rollback()
            raise
        # --- END ATOMIC SECTION ---

        flash("Withdrawal request submitted. You'll be notified when it's processed.", "success")
        return redirect(url_for("referrals.withdrawal_history"))

    return render_template(
        "referrals/withdraw.html",
        wallet_balance=current_user.wallet_balance,
        withdrawable_balance=withdrawable,
        min_withdrawal=MIN_WITHDRAWAL,
    )


@referral_bp.route("/withdrawals")
@login_required
def withdrawal_history():
    withdrawals = WithdrawalRequest.query.filter_by(user_id=current_user.id)\
        .order_by(WithdrawalRequest.created_at.desc()).limit(50).all()

    return render_template("referrals/withdrawals.html", withdrawals=withdrawals)


MIN_WITHDRAWAL = 1000

@referral_bp.route("/withdraw", methods=["GET","POST"])
@login_required
def withdraw():

    if request.method == "POST":
        amount = Decimal(request.form.get("amount", "0"))

        if amount < MIN_WITHDRAWAL:
            flash("Minimum withdrawal is ₦1000", "warning")
            return redirect(url_for("referrals.withdraw"))

        # 🔒 lock row to prevent double-withdraw race condition
        user = User.query.filter_by(id=current_user.id).with_for_update().first()

        if user.wallet_balance < amount:
            flash("Insufficient balance", "danger")
            return redirect(url_for("referrals.withdraw"))

        # reserve funds immediately
        user.wallet_balance -= amount

        req = WithdrawalRequest(
            user_id=user.id,
            amount=amount,
            status="pending"
        )

        db.session.add(req)
        db.session.commit()

        flash("Withdrawal request submitted", "success")
        return redirect(url_for("referrals.withdraw_history"))

    return render_template("referrals/withdraw.html")
