from datetime import datetime
from flask import render_template, url_for
from flask_login import login_required, current_user
from sqlalchemy import func

from . import dashboard_bp
from app.extensions import db
from app.models import User, ReferralEarning
from app.models.quiz import QuizSession, Question
from app.models.campaign_log import CampaignLog


@dashboard_bp.route("/")
@login_required
def index():
    referral_link = url_for("auth.register", ref=current_user.referral_code, _external=True)

    referral_count = (
        db.session.query(func.count(User.id))
        .filter(User.referred_by == current_user.referral_code)
        .scalar()
        or 0
    )

    total_earnings = (
        db.session.query(func.coalesce(func.sum(ReferralEarning.amount), 0))
        .filter(ReferralEarning.referrer_id == current_user.id)
        .scalar()
        or 0
    )

    referred_users = (
        db.session.query(
            User.username,
            User.email,
            func.coalesce(func.sum(ReferralEarning.amount), 0).label("earned")
        )
        .outerjoin(ReferralEarning, ReferralEarning.referred_user_id == User.id)
        .filter(User.referred_by == current_user.referral_code)
        .group_by(User.id, User.username, User.email)
        .order_by(func.coalesce(func.sum(ReferralEarning.amount), 0).desc())
        .limit(200)
        .all()
    )

    active_session = (
        QuizSession.query
        .filter_by(user_id=current_user.id, is_submitted=False)
        .order_by(QuizSession.started_at.desc())
        .first()
    )

    # expire timed-out exams
    if (
        active_session
        and active_session.mode == "exam"
        and active_session.expires_at
        and datetime.utcnow() > active_session.expires_at
    ):
        active_session.is_submitted = True
        active_session.completed_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        active_session = None

    # Admin data
    from app.models import Subscription
    subscribers = []
    active_users = []
    recent_campaigns = []

    # inventory defaults
    inv_bands = []
    inv_qtypes = []
    inv_table = []
    inv_totals_by_qt = {}
    inv_grand_total = 0

    is_admin = bool(getattr(current_user, "is_admin", False))

    if is_admin:
        subscribers = (
            db.session.query(User.username, User.email, Subscription.paid_at)
            .join(Subscription, Subscription.user_id == User.id)
            .filter(Subscription.is_confirmed.is_(True))
            .order_by(Subscription.id.desc())
            .limit(200)
            .all()
        )

        active_users = (
            db.session.query(User.username, User.email)
            .filter(User.is_email_verified.is_(True))
            .order_by(User.id.desc())
            .limit(200)
            .all()
        )

        recent_campaigns = (
            CampaignLog.query
            .order_by(CampaignLog.id.desc())
            .limit(10)
            .all()
        )

        # Question Inventory (Band × Question Type)
        stats_rows = (
            db.session.query(
                Question.band.label("band"),
                Question.question_type.label("qt"),
                func.count(Question.id).label("count"),
            )
            .group_by(Question.band, Question.question_type)
            .all()
        )

        inv_bands = ["l1-4", "l5-7", "l8-10", "l12-14", "l15-16", "l17", "confirmation"]
        inv_qtypes = sorted({r.qt for r in stats_rows if r.qt})

        stats_map = {(r.band, r.qt): int(r.count) for r in stats_rows if r.band and r.qt}

        inv_table = []
        for b in inv_bands:
            row = {"band": b, "total": 0}
            for qt in inv_qtypes:
                c = stats_map.get((b, qt), 0)
                row[qt] = c
                row["total"] += c
            inv_table.append(row)

        inv_totals_by_qt = {qt: sum(r.get(qt, 0) for r in inv_table) for qt in inv_qtypes}
        inv_grand_total = sum(inv_totals_by_qt.values())

    return render_template(
        "dashboard/index.html",
        referral_link=referral_link,
        referral_count=referral_count,
        total_earnings=total_earnings,
        referred_users=referred_users,
        active_session=active_session,
        active_users=active_users,
        subscribers=subscribers,
        recent_campaigns=recent_campaigns,

        is_admin=is_admin,
        inv_bands=inv_bands,
        inv_qtypes=inv_qtypes,
        inv_table=inv_table,
        inv_totals_by_qt=inv_totals_by_qt,
        inv_grand_total=inv_grand_total,
    )