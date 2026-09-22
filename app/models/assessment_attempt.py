from datetime import datetime

from app.extensions import db


class AssessmentAttempt(db.Model):
    __tablename__ = "assessment_attempt"

    id = db.Column(db.Integer, primary_key=True)

    assessment_id = db.Column(
        db.Integer,
        db.ForeignKey("assessment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    started_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    submitted_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="in_progress",
    )

    score = db.Column(
        db.Integer,
        nullable=True,
    )

    total_marks = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    assessment = db.relationship(
        "Assessment",
        backref=db.backref(
            "attempts",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    student = db.relationship(
        "User",
        backref=db.backref(
            "assessment_attempts",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )