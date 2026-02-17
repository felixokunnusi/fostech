"""add rand_key for fast random sampling

Revision ID: 3a1f2c9d6b11
Revises: 20bd88ff0e85
Create Date: 2026-02-15
"""
from alembic import op
import sqlalchemy as sa

revision = "3a1f2c9d6b11"
down_revision = "20bd88ff0e85"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        # SQLite cannot ADD COLUMN with a non-constant default.
        # Step 1: add nullable column WITHOUT default
        op.add_column("question", sa.Column("rand_key", sa.Float(), nullable=True))

        # Step 2: backfill existing rows with a random float in [0, 1)
        # SQLite random() returns a signed 64-bit integer; normalize to [0,1)
        op.execute(
            """
            UPDATE question
            SET rand_key = (abs(random()) / 9223372036854775808.0)
            WHERE rand_key IS NULL
            """
        )

        # Step 3: make it NOT NULL (requires batch mode on SQLite)
        with op.batch_alter_table("question") as batch_op:
            batch_op.alter_column("rand_key", existing_type=sa.Float(), nullable=False)

            # indexes
            batch_op.create_index(
                "ix_question_band_qtype",
                ["band", "question_type"],
                unique=False
            )
            batch_op.create_index(
                "ix_question_band_qtype_rand",
                ["band", "question_type", "rand_key"],
                unique=False
            )

    else:
        # Postgres (Render) — this is what you want in production
        op.add_column(
            "question",
            sa.Column("rand_key", sa.Float(), server_default=sa.text("random()"), nullable=False),
        )
        op.create_index("ix_question_band_qtype", "question", ["band", "question_type"], unique=False)
        op.create_index(
            "ix_question_band_qtype_rand",
            "question",
            ["band", "question_type", "rand_key"],
            unique=False
        )


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("question") as batch_op:
            batch_op.drop_index("ix_question_band_qtype_rand")
            batch_op.drop_index("ix_question_band_qtype")
            batch_op.drop_column("rand_key")
    else:
        op.drop_index("ix_question_band_qtype_rand", table_name="question")
        op.drop_index("ix_question_band_qtype", table_name="question")
        op.drop_column("question", "rand_key")
