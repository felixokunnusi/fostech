from datetime import datetime

from app.extensions import db


class AcademicSession(db.Model):
    __tablename__ = "academic_session"

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
        db.String(50),
        nullable=False,
    )

    start_date = db.Column(
        db.Date,
        nullable=True,
    )

    end_date = db.Column(
        db.Date,
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

    school = db.relationship(
        "School",
        back_populates="academic_sessions",
    )

    def __repr__(self):
        return f"<AcademicSession {self.name}>"