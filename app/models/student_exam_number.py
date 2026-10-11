
from datetime import datetime

from sqlalchemy import UniqueConstraint

from app.extensions import db


class StudentExamNumber(db.Model):
    __tablename__ = "student_exam_number"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    school_id = db.Column(
        db.Integer,
        db.ForeignKey("school.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    academic_session_id = db.Column(
        db.Integer,
        db.ForeignKey("academic_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    exam_number = db.Column(
        db.String(50),
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    student = db.relationship("User")
    school = db.relationship("School")
    academic_session = db.relationship("AcademicSession")

    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "academic_session_id",
            "exam_number",
            name="uq_student_exam_number_school_session_number",
        ),
        UniqueConstraint(
            "student_id",
            "school_id",
            "academic_session_id",
            name="uq_student_exam_number_student_school_session",
        ),
    )

    def __repr__(self):
        return (
            f"<StudentExamNumber student={self.student_id} "
            f"session={self.academic_session_id} "
            f"number={self.exam_number}>"
        )
