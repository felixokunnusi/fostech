from datetime import datetime

from app.extensions import db


class School(db.Model):
    __tablename__ = "school"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(255),
        nullable=False,
        unique=True,
    )

    short_name = db.Column(
        db.String(100),
        nullable=True,
    )

    address = db.Column(
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

    academic_sessions = db.relationship(
        "AcademicSession",
        back_populates="school",
        cascade="all, delete-orphan",
        lazy=True,
    )

    classes = db.relationship(
        "SchoolClass",
        back_populates="school",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def __repr__(self):
        return f"<School {self.name}>"