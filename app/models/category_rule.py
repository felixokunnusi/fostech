from datetime import datetime

from app.extensions import db


class CategoryRule(db.Model):
    __tablename__ = "category_rule"

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

    required = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    minimum_subjects = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    maximum_subjects = db.Column(
        db.Integer,
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

    school = db.relationship("School")

    category = db.relationship(
        "SubjectCategory",
        backref=db.backref(
            "category_rules",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    def __repr__(self):
        return f"<CategoryRule {self.category_id}>"