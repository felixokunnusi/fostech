"""
Assessment Model

Stores teacher-created assessments/assignments.

An assessment belongs to a teacher and can later contain
multiple assessment questions and student submissions.
"""

from datetime import datetime

from app.extensions import db


class Assessment(db.Model):
    __tablename__ = "assessment"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "user.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    title = db.Column(
        db.String(255),
        nullable=False,
    )

    subject = db.Column(
        db.String(150),
        nullable=False,
    )

    class_name = db.Column(
        db.String(100),
        nullable=False,
    )

    topic = db.Column(
        db.String(255),
        nullable=True,
    )

    assessment_type = db.Column(
        db.String(30),
        nullable=False,
        default="mixed",
    )

    mode = db.Column(
    db.String(20),
    nullable=False,
    default="practice",
    )

    instructions = db.Column(
        db.Text,
        nullable=True,
    )

    total_marks = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    start_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    due_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="draft",
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

    teacher = db.relationship(
        "User",
        backref=db.backref(
            "assessments",
            lazy=True,
        ),
    )

    def __repr__(self):
        return (
            f"<Assessment {self.id} "
            f"{self.title}>"
        )