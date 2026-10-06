from datetime import datetime

from app.extensions import db


class StudentSubjectSelection(db.Model):
    __tablename__ = "student_subject_selection"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "user.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
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

    academic_session_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "academic_session.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
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

    class_group_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "class_group.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending",
        index=True,
    )

    submitted_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    reviewed_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    reviewed_by = db.Column(
        db.Integer,
        db.ForeignKey(
            "user.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    review_note = db.Column(
        db.Text,
        nullable=True,
    )

    student = db.relationship(
        "User",
        foreign_keys=[student_id],
        backref=db.backref(
            "subject_selections",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    reviewer = db.relationship(
        "User",
        foreign_keys=[reviewed_by],
    )

    school = db.relationship("School")

    academic_session = db.relationship(
        "AcademicSession",
    )

    school_class = db.relationship(
        "SchoolClass",
    )

    class_group = db.relationship(
        "ClassGroup",
    )

    items = db.relationship(
        "StudentSubjectSelectionItem",
        back_populates="selection",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def __repr__(self):
        return (
            f"<StudentSubjectSelection "
            f"id={self.id} "
            f"student={self.student_id} "
            f"status={self.status}>"
        )


class StudentSubjectSelectionItem(db.Model):
    __tablename__ = "student_subject_selection_item"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    selection_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "student_subject_selection.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    subject_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "school_subject.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    selection = db.relationship(
        "StudentSubjectSelection",
        back_populates="items",
    )

    subject = db.relationship(
        "SchoolSubject",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "selection_id",
            "subject_id",
            name="uq_selection_subject",
        ),
    )

    def __repr__(self):
        return (
            f"<StudentSubjectSelectionItem "
            f"selection={self.selection_id} "
            f"subject={self.subject_id}>"
        )