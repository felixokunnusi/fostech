"""add user role

Revision ID: 169733d0f0fd
Revises: c8a6ad124cdf
Create Date: 2026-09-14 13:45:07.254878

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '169733d0f0fd'
down_revision = 'c8a6ad124cdf'
branch_labels = None
depends_on = None


def upgrade():
    # Add the role column temporarily as nullable so that
    # existing users can be safely migrated.
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'role',
                sa.String(length=20),
                nullable=True
            )
        )

    # Existing users are staff.
    op.execute(
        "UPDATE user SET role = 'staff' WHERE role IS NULL"
    )

    # Make the role column mandatory after existing users
    # have been assigned their role.
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column(
            'role',
            existing_type=sa.String(length=20),
            nullable=False
        )


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('role')