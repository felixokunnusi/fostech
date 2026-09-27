from datetime import datetime

from app.extensions import db


class TeacherSubjectAssignment(db.Model):
    __tablename__ = "teacher_subject_assignment"

    id = db.Column(db.Integer, primary_key=True)

    teacher_id = db.Column(
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

    subject_id = db.Column(
        db.Integer,
        db.ForeignKey("school_subject.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    class_id = db.Column(
        db.Integer,
        db.ForeignKey("school_class.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    class_group_id = db.Column(
        db.Integer,
        db.ForeignKey("class_group.id", ondelete="SET NULL"),
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

    teacher = db.relationship("User")

    school = db.relationship("School")

    academic_session = db.relationship("AcademicSession")

    subject = db.relationship("SchoolSubject")

    school_class = db.relationship("SchoolClass")

    class_group = db.relationship("ClassGroup")

    def __repr__(self):
        return (
            f"<TeacherSubjectAssignment "
            f"teacher={self.teacher_id} "
            f"school={self.school_id} "
            f"subject={self.subject_id}>"
        )