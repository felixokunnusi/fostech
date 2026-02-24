# app/quiz/routes.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from flask import (
    render_template,
    redirect,
    url_for,
    request,
    flash,
    jsonify,
    current_app,
)
from flask_login import login_required, current_user
from sqlalchemy import desc, func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.subscription import Subscription
from app.models.quiz import Question, Choice, QuizSession, UserAnswer
from app.services.difficulty import level_to_band
from app.services.question_selector import pick_questions_fast
from . import quiz_bp


# -------------------- constants --------------------

LABELS = {
    "fr": "Financial Regulation",
    "psr": "Public Service Rule",
    "edu": "Education",
    "gk": "General Knowledge",
}

# ✅ DB truth
ALLOWED_BANDS = ["l1-4", "l5-7", "l8-10", "l12-14", "l15-16", "l17", "confirmation"]


# -------------------- helpers --------------------

def user_is_subscribed(user) -> bool:
    """Active subscription = confirmed + not expired."""
    now = datetime.utcnow()
    sub = (
        Subscription.query
        .filter(
            Subscription.user_id == user.id,
            Subscription.is_confirmed.is_(True),
            Subscription.expires_at.isnot(None),
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
        .first()
    )
    return sub is not None


def needed_count(is_paid: bool) -> int:
    return (
        current_app.config["EXAM_QUESTION_COUNT"]
        if is_paid
        else current_app.config["TRIAL_QUESTION_COUNT"]
    )


def exam_expires_at() -> datetime:
    return datetime.utcnow() + timedelta(
        minutes=current_app.config["EXAM_DURATION_MINUTES"]
    )


def get_trial_questions_for_band(band: str, qt: str, limit: int) -> list[Question]:
    """
    Trial = random questions from DB.
    IMPORTANT: no .distinct(Question.id) here (Postgres DISTINCT ON + random() issue).
    """
    return (
        Question.query
        .filter_by(band=band, question_type=qt)
        .order_by(func.random())
        .limit(limit)
        .all()
    )


def dedupe_keep_order(selected: list[Any]) -> list[Any]:
    """Hard de-dupe while preserving order."""
    seen: set[int] = set()
    out: list[Any] = []
    for q in selected:
        qid = q.id if hasattr(q, "id") else int(q)
        if qid not in seen:
            seen.add(qid)
            out.append(q)
    return out


def resolve_band(level: str) -> str | None:
    """
    Convert /start/<level> to DB band values (l1-4..l17).
    Handles:
      - level == "confirmation"
      - numeric levels ("1", "2", ...)
      - already-normalized ("l1-4") if you ever pass it
    """
    if level == "confirmation":
        return "confirmation"

    # if someone hits /start/l1-4 directly
    if level.startswith("l") and level in ALLOWED_BANDS:
        return level

    try:
        # Your level_to_band MUST return one of: l1-4, l5-7, ...
        band = level_to_band(level)
    except ValueError:
        return None

    return band if band in ALLOWED_BANDS else None


# -------------------- routes --------------------

@quiz_bp.route("/")
@login_required
def choose_level():
    qtypes = [
        r[0]
        for r in db.session.query(Question.question_type)
        .distinct()
        .order_by(Question.question_type.asc())
        .all()
        if r[0]
    ]
    return render_template("quiz/choose_level.html", qtypes=qtypes, labels=LABELS)


@quiz_bp.route("/history")
@login_required
def history():
    mode = request.args.get("mode", "").strip()  # "exam" / "trial"
    band = request.args.get("band", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = 20

    base = QuizSession.query.filter(QuizSession.user_id == current_user.id)

    if mode:
        base = base.filter(QuizSession.mode == mode)
    if band:
        base = base.filter(QuizSession.band == band)

    submitted = base.filter(QuizSession.is_submitted.is_(True))

    overall_count = submitted.count()
    all_rows = submitted.with_entities(QuizSession.score, QuizSession.total_questions).all()
    percents = [
        round((s or 0) / (t or 1) * 100, 2) if (t and t > 0) else 0.0
        for (s, t) in all_rows
    ]
    overall_avg = round(sum(percents) / len(percents), 2) if percents else 0.0
    overall_best = max(percents) if percents else 0.0

    q = base.order_by(desc(QuizSession.started_at), desc(QuizSession.id))
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    sessions = pagination.items

    rows = []
    for s in sessions:
        total = s.total_questions or 0
        score = s.score or 0
        percent = round((score / total) * 100, 2) if total else 0.0

        duration_min = None
        if s.is_submitted and s.completed_at and s.started_at:
            delta = s.completed_at - s.started_at
            duration_min = max(0, int(delta.total_seconds() // 60))

        rows.append({
            "id": s.id,
            "mode": s.mode,
            "band": s.band,
            "is_submitted": bool(s.is_submitted),
            "started_at": s.started_at,
            "completed_at": s.completed_at,
            "score": score,
            "total": total,
            "percent": percent,
            "duration_min": duration_min,
        })

    trend_q = (
        submitted
        .filter(QuizSession.completed_at.isnot(None))
        .order_by(desc(QuizSession.completed_at))
        .limit(12)
        .all()
    )
    trend_q = list(reversed(trend_q))  # oldest -> newest

    trend_points = []
    for s in trend_q:
        total = s.total_questions or 0
        score = s.score or 0
        percent = round((score / total) * 100, 2) if total else 0.0
        label = s.completed_at.strftime("%b %d") if s.completed_at else f"#{s.id}"
        trend_points.append({"label": label, "percent": percent})

    return render_template(
        "quiz/history.html",
        rows=rows,
        pagination=pagination,
        trend_points=trend_points,
        mode=mode,
        band=band,
        bands=ALLOWED_BANDS,
        overall_count=overall_count,
        overall_avg=overall_avg,
        overall_best=overall_best,
    )


@quiz_bp.post("/autosave/<int:session_id>/<int:question_id>")
@login_required
def autosave(session_id: int, question_id: int):
    session = QuizSession.query.get_or_404(session_id)

    if session.user_id != current_user.id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    if session.is_submitted:
        return jsonify({"ok": False, "error": "Already submitted"}), 400

    data = request.get_json(silent=True) or {}
    choice_id = data.get("choice_id")

    if not choice_id:
        return jsonify({"ok": False, "error": "Missing choice_id"}), 400

    choice = Choice.query.get(int(choice_id))
    if not choice or choice.question_id != question_id:
        return jsonify({"ok": False, "error": "Invalid choice"}), 400

    existing = UserAnswer.query.filter_by(session_id=session.id, question_id=question_id).first()
    if existing:
        existing.choice_id = int(choice_id)
    else:
        db.session.add(UserAnswer(
            session_id=session.id,
            question_id=question_id,
            choice_id=int(choice_id),
        ))

    db.session.commit()
    return jsonify({"ok": True})


@quiz_bp.route("/start/<level>")
@login_required
def start(level: str):
    qt = request.args.get("qt", type=str)
    if not qt:
        flash("Please select a question type.", "warning")
        return redirect(url_for("quiz.choose_level"))

    is_paid = user_is_subscribed(current_user)
    mode = "exam" if is_paid else "trial"
    needed = needed_count(is_paid)

    band = resolve_band(level)
    if not band:
        flash("Invalid level selected.", "warning")
        return redirect(url_for("quiz.choose_level"))

    # pick questions (paid uses fast picker; trial uses DB random)
    if is_paid:
        selected = pick_questions_fast(band, qt, needed)
        expires_at = exam_expires_at()
    else:
        selected = get_trial_questions_for_band(band, qt, needed)
        expires_at = None

    selected = dedupe_keep_order(selected)

    if len(selected) < needed:
        total = Question.query.filter_by(band=band, question_type=qt).count()
        flash(
            f"Not enough UNIQUE questions for this selection. Needed {needed}, available {total}.",
            "warning"
        )
        return redirect(url_for("quiz.choose_level"))

    session = QuizSession(
        user_id=current_user.id,
        band=band,
        mode=mode,
        total_questions=needed,
        question_ids_csv=",".join(str(q.id) for q in selected),
        expires_at=expires_at,
    )

    db.session.add(session)
    db.session.commit()

    return redirect(url_for("quiz.take", session_id=session.id, q=1))


@quiz_bp.route("/take/<int:session_id>", methods=["GET", "POST"])
@login_required
def take(session_id: int):
    session = QuizSession.query.get_or_404(session_id)

    if session.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("dashboard.index"))

    if session.is_submitted:
        return redirect(url_for("quiz.result", session_id=session.id))

    # Timer (exam)
    if session.mode == "exam" and session.expires_at and datetime.utcnow() > session.expires_at:
        session.is_submitted = True
        session.completed_at = datetime.utcnow()
        db.session.commit()
        return redirect(url_for("quiz.result", session_id=session.id))

    question_ids = session.get_question_ids()
    if not question_ids:
        flash("This session has no questions.", "warning")
        return redirect(url_for("quiz.choose_level"))

    q_index = int(request.args.get("q", 1))
    q_index = max(1, min(q_index, len(question_ids)))

    current_q_id = question_ids[q_index - 1]
    question = Question.query.get_or_404(current_q_id)

    if request.method == "POST":
        chosen_id = request.form.get("choice_id")

        if chosen_id:
            existing = UserAnswer.query.filter_by(session_id=session.id, question_id=question.id).first()
            if existing:
                existing.choice_id = int(chosen_id)
            else:
                db.session.add(UserAnswer(
                    session_id=session.id,
                    question_id=question.id,
                    choice_id=int(chosen_id)
                ))
            db.session.commit()

        action = request.form.get("action") or request.form.get("action_field")

        if action == "submit":
            session.is_submitted = True
            session.completed_at = datetime.utcnow()
            db.session.commit()
            return redirect(url_for("quiz.result", session_id=session.id))

        if action == "next":
            return redirect(url_for("quiz.take", session_id=session.id, q=q_index + 1))

        if action == "prev":
            return redirect(url_for("quiz.take", session_id=session.id, q=q_index - 1))

        jump_to = request.form.get("jump_to")
        if jump_to:
            return redirect(url_for("quiz.take", session_id=session.id, q=int(jump_to)))

    answered_q_ids = {
        a.question_id for a in UserAnswer.query.filter_by(session_id=session.id).all()
    }

    existing_answer = UserAnswer.query.filter_by(
        session_id=session.id,
        question_id=question.id
    ).first()

    selected_choice_id = existing_answer.choice_id if existing_answer else None

    remaining_seconds = None
    if session.mode == "exam" and session.expires_at:
        remaining_seconds = max(
            0,
            int((session.expires_at - datetime.utcnow()).total_seconds())
        )

    grid_count = current_app.config.get("GRID_QUESTION_COUNT", len(question_ids))

    return render_template(
        "quiz/take.html",
        session=session,
        question=question,
        choices=question.choices,
        q_index=q_index,
        total=len(question_ids),
        question_ids=question_ids,
        answered_q_ids=answered_q_ids,
        selected_choice_id=selected_choice_id,
        remaining_seconds=remaining_seconds,
        grid_count=grid_count,
    )


@quiz_bp.route("/result/<int:session_id>")
@login_required
def result(session_id: int):
    session = QuizSession.query.get_or_404(session_id)

    if session.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("dashboard.index"))

    q_ids = session.get_question_ids()
    if not q_ids:
        flash("No questions found for this session.", "warning")
        return redirect(url_for("quiz.choose_level"))

    questions = (
        Question.query
        .options(joinedload(Question.choices))
        .filter(Question.id.in_(q_ids))
        .all()
    )
    q_map = {q.id: q for q in questions}

    answers = UserAnswer.query.filter_by(session_id=session.id).all()
    ans_map = {a.question_id: a.choice_id for a in answers}

    total = len([qid for qid in q_ids if qid])
    answered = len(ans_map)
    unanswered = max(0, total - answered)

    correct = 0
    wrong = 0
    review = []

    for idx, qid in enumerate(q_ids, start=1):
        q = q_map.get(qid)
        if not q:
            continue

        correct_choice = next((c for c in q.choices if c.is_correct), None)
        user_choice_id = ans_map.get(q.id)
        user_choice = next((c for c in q.choices if c.id == user_choice_id), None)

        if user_choice_id is None:
            status = "unanswered"
        elif correct_choice and user_choice_id == correct_choice.id:
            status = "correct"
            correct += 1
        else:
            status = "wrong"
            wrong += 1

        review.append({
            "number": idx,
            "question_id": q.id,
            "question_text": q.text,
            "choices": q.choices,
            "user_choice_id": user_choice_id,
            "user_choice_text": user_choice.text if user_choice else None,
            "correct_choice_id": correct_choice.id if correct_choice else None,
            "correct_choice_text": correct_choice.text if correct_choice else None,
            "explanation": q.explanation,
            "status": status,
        })

    session.score = correct
    db.session.commit()

    percent = round((correct / total) * 100, 2) if total else 0.0

    return render_template(
        "quiz/result.html",
        session=session,
        percent=percent,
        total=total,
        answered=answered,
        unanswered=unanswered,
        correct=correct,
        wrong=wrong,
        review=review,
    )