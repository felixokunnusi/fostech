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
from app.services.paystack_banks import fetch_banks  # ✅ NEW


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
    MIN_WITHDRAWAL = _money(current_app.config.get("MIN_WITHDRAWAL_AMOUNT", "1000"))

    # compute withdrawable (wallet - pending)
    withdrawable = _money(get_withdrawable_balance(current_user.id, current_user.wallet_balance))

    # ✅ Fetch banks for dropdown (GET and POST so template can re-render on errors)
    banks = fetch_banks(current_app.config.get("PAYSTACK_SECRET_KEY", ""))

    if request.method == "POST":
        raw_amount = (request.form.get("amount") or "").strip()

        # ✅ NEW: bank_code comes from dropdown; bank_name comes from hidden field
        bank_code = (request.form.get("bank_code") or "").strip()
        bank_name = (request.form.get("bank_name") or "").strip()

        account_name = (request.form.get("account_name") or "").strip()
        account_number = (request.form.get("account_number") or "").strip()

        # Validate amount
        try:
            amount = _money(raw_amount)
        except (InvalidOperation, TypeError):
            flash("Enter a valid withdrawal amount.", "danger")
            return render_template(
                "referrals/withdraw.html",
                wallet_balance=current_user.wallet_balance,
                withdrawable_balance=withdrawable,
                min_withdrawal=MIN_WITHDRAWAL,
                banks=banks,
            )

        if amount <= Decimal("0.00"):
            flash("Amount must be greater than ₦0.", "danger")
            return render_template(
                "referrals/withdraw.html",
                wallet_balance=current_user.wallet_balance,
                withdrawable_balance=withdrawable,
                min_withdrawal=MIN_WITHDRAWAL,
                banks=banks,
            )

        # ✅ Minimum withdrawal enforcement
        if amount < MIN_WITHDRAWAL:
            flash(f"Minimum withdrawal is ₦{MIN_WITHDRAWAL:,.2f}.", "warning")
            return render_template(
                "referrals/withdraw.html",
                wallet_balance=current_user.wallet_balance,
                withdrawable_balance=withdrawable,
                min_withdrawal=MIN_WITHDRAWAL,
                banks=banks,
            )

        # ✅ Validate bank fields (bank_code is required for Paystack)
        if not (bank_code and bank_name and account_name and account_number):
            flash("Please select your bank and fill in your account details.", "danger")
            return render_template(
                "referrals/withdraw.html",
                wallet_balance=current_user.wallet_balance,
                withdrawable_balance=withdrawable,
                min_withdrawal=MIN_WITHDRAWAL,
                banks=banks,
            )

        # Optional: basic account number validation
        if not account_number.isdigit() or len(account_number) != 10:
            flash("Account number must be 10 digits.", "danger")
            return render_template(
                "referrals/withdraw.html",
                wallet_balance=current_user.wallet_balance,
                withdrawable_balance=withdrawable,
                min_withdrawal=MIN_WITHDRAWAL,
                banks=banks,
            )

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
                return render_template(
                    "referrals/withdraw.html",
                    wallet_balance=current_user.wallet_balance,
                    withdrawable_balance=withdrawable,
                    min_withdrawal=MIN_WITHDRAWAL,
                    banks=banks,
                )
            fee = (amount * Decimal("0.10")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            net_amount = _money(amount - fee)

            if net_amount <= Decimal("0.00"):
                flash("Amount too small after processing fee.", "danger")
                db.session.rollback()
                return render_template(...)

            wr = WithdrawalRequest(
                user_id=user_row.id,
                amount=amount,
                fee=fee,
                net_amount=net_amount,
                bank_code=bank_code,
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
        banks=banks,  # ✅ NEW
    )

@referral_bp.route("/withdrawals")
@login_required
def withdrawal_history():
    withdrawals = WithdrawalRequest.query.filter_by(user_id=current_user.id)\
        .order_by(WithdrawalRequest.created_at.desc()).limit(50).all()

    return render_template("referrals/withdrawals.html", withdrawals=withdrawals)

