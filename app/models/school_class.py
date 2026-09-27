from datetime import datetime

from app.extensions import db


class SchoolClass(db.Model):
    __tablename__ = "school_class"

    id = db.Column(db.Integer, primary_key=True)

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

    display_order = db.Column(
        db.Integer,
        nullable=False,
        default=0,
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
        back_populates="classes",
    )

    groups = db.relationship(
        "ClassGroup",
        back_populates="school_class",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def __repr__(self):
        return f"<SchoolClass {self.name}>"