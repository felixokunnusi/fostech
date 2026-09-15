"""replace single user type with multiple user roles

Revision ID: b5df784939f0
Revises: 2c7946149576
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b5df784939f0"
down_revision = "2c7946149576"
branch_labels = None
depends_on = None


def upgrade():
    # ----------------------------------------------------------
    # 1. Create the new user_role table
    # ----------------------------------------------------------
    op.create_table(
        "user_role",

        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="CASCADE"
        ),

        sa.PrimaryKeyConstraint(
            "user_id",
            "role"
        )
    )

    # ----------------------------------------------------------
    # 2. Transfer existing user types into user_role
    # ----------------------------------------------------------
    #
    # Every existing user currently has a value in user_type.
    #
    # Example:
    #
    #     user.id = 8
    #     user_type = civil_servant
    #
    # becomes:
    #
    #     user_role
    #     user_id = 8
    #     role = civil_servant
    #
    # ----------------------------------------------------------
    op.execute(
        """
        INSERT INTO user_role (user_id, role)
        SELECT id, user_type
        FROM user
        WHERE user_type IS NOT NULL
        """
    )

    # ----------------------------------------------------------
    # 3. Remove the old single-role column
    # ----------------------------------------------------------
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("user_type")


def downgrade():
    # ----------------------------------------------------------
    # 1. Restore the old user_type column
    # ----------------------------------------------------------
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "user_type",
                sa.String(length=20),
                nullable=True
            )
        )

    # ----------------------------------------------------------
    # 2. Restore one role per user
    # ----------------------------------------------------------
    #
    # A previous multi-role state cannot be represented perfectly
    # by the old single user_type column.
    #
    # We therefore select one role using this priority:
    #
    #     civil_servant
    #     teacher
    #     student
    #
    # ----------------------------------------------------------
    op.execute(
        """
        UPDATE user
        SET user_type = (
            SELECT ur.role
            FROM user_role ur
            WHERE ur.user_id = user.id
            ORDER BY
                CASE ur.role
                    WHEN 'civil_servant' THEN 1
                    WHEN 'teacher' THEN 2
                    WHEN 'student' THEN 3
                    ELSE 4
                END
            LIMIT 1
        )
        """
    )

    # ----------------------------------------------------------
    # 3. Make user_type non-null again
    # ----------------------------------------------------------
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.alter_column(
            "user_type",
            existing_type=sa.String(length=20),
            nullable=False
        )

    # ----------------------------------------------------------
    # 4. Remove the new role table
    # ----------------------------------------------------------
    op.drop_table("user_role")