"""replace role with user type and staff access

Revision ID: 2c7946149576
Revises: 169733d0f0fd
Create Date: 2026-09-14 15:22:36.356421

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2c7946149576'
down_revision = '169733d0f0fd'
branch_labels = None
depends_on = None


def upgrade():
    # ----------------------------------------------------------
    # STEP 1: Add the new columns temporarily as nullable.
    # This is necessary because the existing user table already
    # contains users.
    # ----------------------------------------------------------
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'user_type',
                sa.String(length=20),
                nullable=True
            )
        )

        batch_op.add_column(
            sa.Column(
                'is_staff',
                sa.Boolean(),
                nullable=True
            )
        )

    # ----------------------------------------------------------
    # STEP 2: Preserve the existing role information.
    #
    # Existing:
    #     role = civil_servant
    #
    # Becomes:
    #     user_type = civil_servant
    # ----------------------------------------------------------
    op.execute(
        """
        UPDATE user
        SET user_type = role
        WHERE user_type IS NULL
        """
    )

    # ----------------------------------------------------------
    # STEP 3: Existing users are NOT organizational staff.
    # Therefore their new staff-access flag is False.
    # ----------------------------------------------------------
    op.execute(
        """
        UPDATE user
        SET is_staff = 0
        WHERE is_staff IS NULL
        """
    )

    # ----------------------------------------------------------
    # STEP 4: Now that existing records have valid values,
    # make both columns mandatory.
    # ----------------------------------------------------------
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column(
            'user_type',
            existing_type=sa.String(length=20),
            nullable=False
        )

        batch_op.alter_column(
            'is_staff',
            existing_type=sa.Boolean(),
            nullable=False
        )

    # ----------------------------------------------------------
    # STEP 5: Remove the old role column.
    # ----------------------------------------------------------
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('role')


def downgrade():
    # ----------------------------------------------------------
    # Restore the old role column temporarily as nullable.
    # ----------------------------------------------------------
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'role',
                sa.String(length=20),
                nullable=True
            )
        )

    # Restore role from user_type.
    op.execute(
        """
        UPDATE user
        SET role = user_type
        WHERE role IS NULL
        """
    )

    # Make role mandatory again.
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column(
            'role',
            existing_type=sa.String(length=20),
            nullable=False
        )

    # Remove the new columns.
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('is_staff')
        batch_op.drop_column('user_type')