from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import Numeric, CheckConstraint
from decimal import Decimal


# ==========================================================
# USER ROLES ASSOCIATION TABLE
# ==========================================================
#
# A user can have more than one primary role.
#
# Supported roles:
#     civil_servant
#     teacher
#     student
#
# Staff is NOT stored here.
# Staff access is controlled separately by User.is_staff.
#
# Example:
#
#     User A
#         civil_servant
#         teacher
#
#     User B
#         student
#
#     User C
#         civil_servant
#         teacher
#         is_staff = True
#
# ==========================================================

user_roles = db.Table(
    "user_roles",

    db.Column(
        "user_id",
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True
    ),

    db.Column(
        "role",
        db.String(20),
        primary_key=True
    )
)


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(256),
        nullable=False
    )

    # ----------------------------------------------------------
    # USER ROLES
    # ----------------------------------------------------------
    # A user may have one or more roles:
    #
    #     civil_servant
    #     teacher
    #     student
    #
    # Staff is NOT a role here.
    # ----------------------------------------------------------
    roles = db.relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy=True
    )

    # ----------------------------------------------------------
    # STAFF ACCESS
    # ----------------------------------------------------------
    # Staff is an additional privilege/access layer.
    #
    # A user can therefore be:
    #
    #     civil servant + staff
    #     teacher + staff
    #     student + staff
    #     civil servant + teacher + staff
    #
    # without changing their primary roles.
    # ----------------------------------------------------------
    is_staff = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    is_email_verified = db.Column(
        db.Boolean,
        default=False
    )

    email_confirm_code = db.Column(
        db.String(6),
        nullable=True
    )

    referral_code = db.Column(
        db.String(10),
        unique=True
    )

    referred_by = db.Column(
        db.String(10)
    )

    is_admin = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    email_code_sent_at = db.Column(
        db.DateTime
    )

    email_confirm_expires = db.Column(
        db.DateTime
    )

    last_confirmation_sent = db.Column(
        db.DateTime
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    reset_token = db.Column(
        db.String(255),
        index=True
    )

    reset_token_expires = db.Column(
        db.DateTime
    )

    wallet_balance = db.Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00")
    )

    current_session_token = db.Column(
        db.String(128),
        nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "wallet_balance >= 0",
            name="wallet_balance_non_negative"
        ),
    )

    # ----------------------------------------------------------
    # SUBSCRIPTIONS
    # ----------------------------------------------------------
    subscriptions = db.relationship(
        "Subscription",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # ----------------------------------------------------------
    # PASSWORD METHODS
    # ----------------------------------------------------------
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )


class UserRole(db.Model):
    """
    Represents one primary role assigned to a user.

    Valid roles:

        civil_servant
        teacher
        student
    """

    __tablename__ = "user_role"

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True
    )

    role = db.Column(
        db.String(20),
        primary_key=True
    )

    user = db.relationship(
        "User",
        back_populates="roles"
    )