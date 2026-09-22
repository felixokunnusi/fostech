from datetime import datetime

from app.extensions import db


class AssessmentAnswer(db.Model):
    __tablename__ = "assessment_answer"

    id = db.Column(db.Integer, primary_key=True)

    attempt_id = db.Column(
        db.Integer,
        db.ForeignKey("assessment_attempt.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    question_id = db.Column(
        db.Integer,
        db.ForeignKey("assessment_question.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    answer_text = db.Column(
        db.Text,
        nullable=True,
    )

    marks_awarded = db.Column(
        db.Integer,
        nullable=True,
    )

    is_correct = db.Column(
        db.Boolean,
        nullable=True,
    )

    teacher_feedback = db.Column(
        db.Text,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    attempt = db.relationship(
        "AssessmentAttempt",
        backref=db.backref(
            "answers",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    question = db.relationship(
        "AssessmentQuestion",
        backref=db.backref(
            "student_answers",
            lazy=True,
        ),
    )