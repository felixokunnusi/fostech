from datetime import datetime

from app.extensions import db


class StudentSubjectEnrollment(db.Model):
    __tablename__ = "student_subject_enrollment"

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

    subject_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "school_subject.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    enrolled_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    student = db.relationship(
        "User",
        backref=db.backref(
            "subject_enrollments",
            lazy=True,
            cascade="all, delete-orphan",
        ),
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

    subject = db.relationship(
        "SchoolSubject",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "student_id",
            "school_id",
            "academic_session_id",
            "class_id",
            "class_group_id",
            "subject_id",
            name="uq_student_subject_enrollment_context",
        ),
    )

    def __repr__(self):
        return (
            f"<StudentSubjectEnrollment "
            f"student={self.student_id} "
            f"subject={self.subject_id}>"
        )