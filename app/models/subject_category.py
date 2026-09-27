from datetime import datetime

from app.extensions import db


class SubjectCategory(db.Model):
    __tablename__ = "subject_category"

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
        index=True,
    )

    name = db.Column(
        db.String(100),
        nullable=False,
    )

    description = db.Column(
        db.Text,
        nullable=True,
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
            "subject_categories",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    subjects = db.relationship(
        "SchoolSubject",
        back_populates="category",
        lazy=True,
    )

    class_groups = db.relationship(
        "ClassGroup",
        back_populates="category",
        lazy=True,
    )

    def __repr__(self):
        return f"<SubjectCategory {self.name}>"