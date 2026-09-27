from datetime import datetime

from app.extensions import db


class SchoolSubject(db.Model):
    __tablename__ = "school_subject"

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
        db.String(150),
        nullable=False,
    )

    code = db.Column(
        db.String(50),
        nullable=True,
    )

    category_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "subject_category.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
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
            "subjects",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    category = db.relationship(
        "SubjectCategory",
        back_populates="subjects",
    )

    def __repr__(self):
        return f"<SchoolSubject {self.name}>"