from datetime import datetime

from app.extensions import db


class SubjectSelectionRule(db.Model):
    __tablename__ = "subject_selection_rule"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    school_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "school.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    minimum_subjects = db.Column(
        db.Integer,
        nullable=False,
        default=8,
    )

    maximum_subjects = db.Column(
        db.Integer,
        nullable=False,
        default=9,
    )

    active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    school = db.relationship(
        "School",
        backref=db.backref(
            "subject_selection_rule",
            uselist=False,
            cascade="all, delete-orphan",
        ),
    )

    def __repr__(self):
        return (
            f"<SubjectSelectionRule "
            f"school={self.school_id} "
            f"min={self.minimum_subjects} "
            f"max={self.maximum_subjects}>"
        )