# app/services/question_selector.py
from __future__ import annotations

from typing import List

from sqlalchemy import case, func

from app.extensions import db
from app.models.quiz import Question


def pick_questions_fast(band: str, qt: str, needed: int) -> List[Question]:
    """
    Postgres-safe random picker that returns Questions in the same random order
    as the sampled IDs.

    - No DISTINCT ON => avoids Postgres ORDER BY constraints.
    - Unique by construction (Question.id is a PK and we're querying only Question.id).
    """

    # 1) Pick random IDs (unique because Question.id is unique and there's no join)
    id_rows = (
        db.session.query(Question.id)
        .filter(Question.band == band, Question.question_type == qt)
        .order_by(func.random())
        .limit(needed)
        .all()
    )
    ids = [row[0] for row in id_rows]

    if not ids:
        return []

    # 2) Load Questions in EXACTLY that sampled order
    # case({id: index, ...}, value=Question.id) creates a stable ordering expression
    ordering = case({qid: i for i, qid in enumerate(ids)}, value=Question.id)

    return (
        Question.query
        .filter(Question.id.in_(ids))
        .order_by(ordering)
        .all()
    )