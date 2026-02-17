import random
from app.models.quiz import Question


def pick_questions_fast(band, qt, limit):
    t = random.random()

    base = Question.query.filter_by(band=band, question_type=qt)

    q1 = (
        base.filter(Question.rand_key >= t)
        .order_by(Question.rand_key)
        .limit(limit)
        .all()
    )

    if len(q1) == limit:
        return q1

    remaining = limit - len(q1)

    q2 = (
        base.filter(Question.rand_key < t)
        .order_by(Question.rand_key)
        .limit(remaining)
        .all()
    )

    return q1 + q2
