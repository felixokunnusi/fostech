import random
from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app.models.subscription import Subscription  # adjust import path to your real one
from app.extensions import db
from app.models.quiz import Question, Choice, QuizSession, UserAnswer
from app.services.difficulty import level_to_band
from . import quiz_bp
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from app.services.question_selector import pick_questions_fast


EXAM_TOTAL_QUESTIONS = 70
EXAM_DURATION_MINUTES = 40
TRIAL_QUESTIONS = 10
EXAM_QUESTION_COUNT = 70
TRIAL_QUESTION_COUNT = 10
GRID_QUESTION_COUNT = 70  # always show 70 in UI

# Exam History 
from sqlalchemy import desc, func
from flask import render_template, request, redirect, url_for
from flask_login import login_required, current_user

@quiz_bp.route("/history")
@login_required
def history():
    mode = request.args.get("mode", "").strip()      # "exam" / "trial"
    band = request.args.get("band", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = 20

    base = QuizSession.query.filter(QuizSession.user_id == current_user.id)

    if mode:
        base = base.filter(QuizSession.mode == mode)
    if band:
        base = base.filter(QuizSession.band == band)

    # Overall stats across ALL filtered attempts (submitted only)
    submitted = base.filter(QuizSession.is_submitted.is_(True))

    overall_count = submitted.count()
    # Percent = score/total*100; do average in Python for simplicity
    all_rows = submitted.with_entities(QuizSession.score, QuizSession.total_questions).all()
    percents = [
        round((s or 0) / (t or 1) * 100, 2) if (t and t > 0) else 0.0
        for (s, t) in all_rows
    ]
    overall_avg = round(sum(percents) / len(percents), 2) if percents else 0.0
    overall_best = max(percents) if percents else 0.0

    # Page list (show in-progress too)
    q = base.order_by(desc(QuizSession.started_at), desc(QuizSession.id))
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    sessions = pagination.items

    rows = []
    for s in sessions:
        total = s.total_questions or 0
        score = s.score or 0
        percent = round((score / total) * 100, 2) if total else 0.0

        # Duration
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

    # Trend (last 12 submitted, completed)
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
        overall_count=overall_count,
        overall_avg=overall_avg,
        overall_best=overall_best,
    )


# Autosave selected options
@quiz_bp.post("/autosave/<int:session_id>/<int:question_id>")
@login_required
def autosave(session_id, question_id):
    session = QuizSession.query.get_or_404(session_id)

    if session.user_id != current_user.id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    if session.is_submitted:
        return jsonify({"ok": False, "error": "Already submitted"}), 400

    data = request.get_json(silent=True) or {}
    choice_id = data.get("choice_id")

    if not choice_id:
        return jsonify({"ok": False, "error": "Missing choice_id"}), 400

    # Optional: ensure the choice belongs to this question
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


def user_is_subscribed(user) -> bool:
    # Adjust this to your real subscription logic:
    # e.g. user.has_active_subscription() if you already have it
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


'''
def get_trial_questions_for_band(band: str, limit: int = TRIAL_QUESTIONS):
    # "Fixed curated" trial set:
    # simplest: just take earliest questions (stable ordering)
    return Question.query.filter_by(band=band).order_by(Question.id.asc()).limit(limit).all()
'''
def get_trial_questions_for_band(band: str, qt: str, limit: int):
    # DB-randomized selection (better than .all()+shuffle for large datasets)
    return (
        Question.query
        .filter_by(band=band, question_type=qt)
        .order_by(func.random())
        .limit(limit)
        .all()
    )


@quiz_bp.route("/")
@login_required
def choose_level():
    # Distinct question_type tags (e.g. psr, fr, etc.)
    qtypes = [
        r[0] for r in db.session.query(Question.question_type)
        .distinct()
        .order_by(Question.question_type.asc())
        .all()
        if r[0]
    ]

    LABELS = {
    "fr": "Financial Regulation",
    "psr": "Public Service Rule",
    "edu": "Education",
    "gk": "General Knowledge",
    }

    return render_template("quiz/choose_level.html", qtypes=qtypes, labels=LABELS)



@quiz_bp.route("/start/<level>")
@login_required
def start(level):
    # required querystring: ?qt=psr (or fr, etc.)
    qt = request.args.get("qt", type=str)
    if not qt:
        flash("Please select a question type.", "warning")
        return redirect(url_for("quiz.choose_level"))

    is_paid = user_is_subscribed(current_user)
    needed = EXAM_TOTAL_QUESTIONS if is_paid else TRIAL_QUESTIONS

    # band selection
    if level == "confirmation":
        band = "confirmation"
    else:
        try:
            band = level_to_band(level)
        except ValueError:
            flash("Invalid level selected.", "warning")
            return redirect(url_for("quiz.choose_level"))

    if is_paid:
        mode = "exam"

        # DB-randomized exam selection
        selected = pick_questions_fast(band, qt, needed)

        if len(selected) < EXAM_TOTAL_QUESTIONS:
            # show how many exist total for that filter
            total = Question.query.filter_by(band=band, question_type=qt).count()
            flash(f"Not enough questions for this selection. Found {total}.", "warning")
            return redirect(url_for("quiz.choose_level"))

        expires_at = datetime.utcnow() + timedelta(minutes=EXAM_DURATION_MINUTES)

    else:
        mode = "trial"
        selected = get_trial_questions_for_band(band, qt, TRIAL_QUESTIONS)

        if len(selected) < TRIAL_QUESTIONS:
            total = Question.query.filter_by(band=band, question_type=qt).count()
            flash(f"Not enough trial questions for this selection. Found {total}.", "warning")
            return redirect(url_for("quiz.choose_level"))

        expires_at = None

    session = QuizSession(
        user_id=current_user.id,
        band=band,
        mode=mode,
        total_questions=len(selected),
        question_ids_csv=",".join(str(q.id) for q in selected),
        expires_at=expires_at,
    )

    db.session.add(session)
    db.session.commit()

    return redirect(url_for("quiz.take", session_id=session.id, q=1))


@quiz_bp.route("/take/<int:session_id>", methods=["GET", "POST"])
@login_required
def take(session_id):
    session = QuizSession.query.get_or_404(session_id)

    # Security: make sure owner
    if session.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("dashboard.index"))

    # prevent re-taking after submission
    if session.is_submitted:
        return redirect(url_for("quiz.result", session_id=session.id))

    # Timer (exam)
    if session.mode == "exam" and session.expires_at and datetime.utcnow() > session.expires_at:
        session.is_submitted = True
        session.completed_at = datetime.utcnow()
        db.session.commit()
        return redirect(url_for("quiz.result", session_id=session.id))

    question_ids = session.get_question_ids()
    q_index = int(request.args.get("q", 1))
    q_index = max(1, min(q_index, len(question_ids)))

    current_q_id = question_ids[q_index - 1]
    question = Question.query.get_or_404(current_q_id)

    if request.method == "POST":
        chosen_id = request.form.get("choice_id")

        # save answer if provided
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

        # jump
        jump_to = request.form.get("jump_to")
        if jump_to:
            return redirect(url_for("quiz.take", session_id=session.id, q=int(jump_to)))

    # build answered map for the icon grid
    answered_q_ids = {
        a.question_id for a in UserAnswer.query.filter_by(session_id=session.id).all()
    }

    # Keep selected options intact when question is revisited
    existing_answer = UserAnswer.query.filter_by(
    session_id=session.id,
    question_id=question.id
    ).first()

    selected_choice_id = existing_answer.choice_id if existing_answer else None


    # remaining time
    remaining_seconds = None
    if session.mode == "exam" and session.expires_at:
        remaining_seconds = max(0, int((session.expires_at - datetime.utcnow()).total_seconds()))

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
    )


# Result route
@quiz_bp.route("/result/<int:session_id>")
@login_required
def result(session_id):
    session = QuizSession.query.get_or_404(session_id)

    if session.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("dashboard.index"))

    q_ids = session.get_question_ids()

    # Load questions + choices in one go
    questions = (
        Question.query
        .options(joinedload(Question.choices))
        .filter(Question.id.in_(q_ids))
        .all()
    )
    q_map = {q.id: q for q in questions}

    # All answers for this session
    answers = UserAnswer.query.filter_by(session_id=session.id).all()
    ans_map = {a.question_id: a.choice_id for a in answers}

    total = len([qid for qid in q_ids if qid])  # ignore blanks if any
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

        status = "unanswered"
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

    # Persist score for session
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
