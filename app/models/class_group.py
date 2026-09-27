from datetime import datetime

from app.extensions import db


class ClassGroup(db.Model):
    __tablename__ = "class_group"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    class_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "school_class.id",
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

    # Academic subject category for this class group.
    # Examples: Science, Business, Humanities, Trade.
    category_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "subject_category.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    school_class = db.relationship(
        "SchoolClass",
        back_populates="groups",
    )

    category = db.relationship(
        "SubjectCategory",
        back_populates="class_groups",
    )

    def __repr__(self):
        return f"<ClassGroup {self.name}>"