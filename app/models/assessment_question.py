"""
Assessment Question Model

Stores individual questions belonging to a teacher-created assessment.

Questions are kept separate from the Assessment model so that each
assessment can contain any number of questions and different question
types.
"""

from datetime import datetime

from app.extensions import db


class AssessmentQuestion(db.Model):
    __tablename__ = "assessment_question"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    assessment_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "assessment.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    question_number = db.Column(
        db.Integer,
        nullable=False,
    )

    question_type = db.Column(
        db.String(30),
        nullable=False,
        default="mcq",
    )

    question_text = db.Column(
        db.Text,
        nullable=False,
    )

    option_a = db.Column(
        db.Text,
        nullable=True,
    )

    option_b = db.Column(
        db.Text,
        nullable=True,
    )

    option_c = db.Column(
        db.Text,
        nullable=True,
    )

    option_d = db.Column(
        db.Text,
        nullable=True,
    )

    correct_answer = db.Column(
        db.Text,
        nullable=True,
    )

    marks = db.Column(
        db.Integer,
        nullable=False,
        default=1,
    )

    explanation = db.Column(
        db.Text,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    assessment = db.relationship(
        "Assessment",
        backref=db.backref(
            "questions",
            lazy=True,
            cascade="all, delete-orphan",
            order_by="AssessmentQuestion.question_number",
        ),
    )

    def __repr__(self):
        return (
            f"<AssessmentQuestion "
            f"{self.assessment_id}-"
            f"{self.question_number}>"
        )