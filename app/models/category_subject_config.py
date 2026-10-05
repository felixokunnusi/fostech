from datetime import datetime

from app.extensions import db


class CategorySubjectConfig(db.Model):
    __tablename__ = "category_subject_config"

    id = db.Column(db.Integer, primary_key=True)

    school_id = db.Column(
        db.Integer,
        db.ForeignKey("school.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("subject_category.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    subject_id = db.Column(
        db.Integer,
        db.ForeignKey("school_subject.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    required = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    is_default = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    selectable = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
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

    school = db.relationship("School")

    category = db.relationship(
        "SubjectCategory",
        backref=db.backref(
            "subject_configs",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    subject = db.relationship("SchoolSubject")

    def __repr__(self):
        return f"<CategorySubjectConfig {self.category_id}:{self.subject_id}>"