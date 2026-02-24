from sqlalchemy import func, case
from app.extensions import db
from app.models.quiz import Question

def pick_questions_fast(band: str, qt: str, needed: int):
    # 1) Pick random unique IDs
    id_rows = (
        db.session.query(Question.id)
        .filter(Question.band == band, Question.question_type == qt)
        .distinct(Question.id)
        .order_by(func.random())
        .limit(needed)
        .all()
    )
    ids = [r[0] for r in id_rows]

    if not ids:
        return []

    # 2) Load questions in the SAME order as ids
    ordering = case({qid: i for i, qid in enumerate(ids)}, value=Question.id)
    return (
        Question.query
        .filter(Question.id.in_(ids))
        .order_by(ordering)
        .all()
    )