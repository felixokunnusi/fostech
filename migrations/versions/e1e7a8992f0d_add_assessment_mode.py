"""add assessment mode

Revision ID: e1e7a8992f0d
Revises: 91eff3c087ad
Create Date: 2026-09-22 14:52:27.580138

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e1e7a8992f0d"
down_revision = "91eff3c087ad"
branch_labels = None
depends_on = None


def upgrade():
    # Add the column with a temporary database default so
    # existing assessment records receive "practice".
    with op.batch_alter_table("assessment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "mode",
                sa.String(length=20),
                nullable=False,
                server_default="practice",
            )
        )

    # Remove the database-level default after existing rows
    # have been populated. The SQLAlchemy model provides
    # the application-level default for new assessments.
    with op.batch_alter_table("assessment", schema=None) as batch_op:
        batch_op.alter_column(
            "mode",
            server_default=None,
        )


def downgrade():
    with op.batch_alter_table("assessment", schema=None) as batch_op:
        batch_op.drop_column("mode")