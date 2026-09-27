from datetime import datetime

from app.extensions import db


class SchoolMembership(db.Model):
    __tablename__ = "school_membership"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
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

    # Optional: useful for staff/teachers and future role-specific placement.
    class_id = db.Column(
        db.Integer,
        db.ForeignKey("school_class.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Optional because not every school/user relationship needs a class group.
    class_group_id = db.Column(
        db.Integer,
        db.ForeignKey("class_group.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Examples:
    # teacher
    # student
    # staff
    # admin
    membership_type = db.Column(
        db.String(30),
        nullable=False,
    )

    active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    joined_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "school_memberships",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    school = db.relationship("School")

    academic_session = db.relationship("AcademicSession")

    school_class = db.relationship("SchoolClass")

    class_group = db.relationship("ClassGroup")

    def __repr__(self):
        return (
            f"<SchoolMembership "
            f"user={self.user_id} "
            f"school={self.school_id} "
            f"session={self.academic_session_id} "
            f"type={self.membership_type}>"
        )