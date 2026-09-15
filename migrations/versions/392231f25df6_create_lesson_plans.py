"""create lesson plans

Revision ID: 392231f25df6
Revises: b5df784939f0
Create Date: 2026-09-15 08:50:59.898865

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "392231f25df6"
down_revision = "b5df784939f0"
branch_labels = None
depends_on = None


def upgrade():
    # ----------------------------------------------------------
    # LESSON PLAN TABLE
    # ----------------------------------------------------------
    op.create_table(
        "lesson_plan",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "format_key",
            sa.String(length=50),
            nullable=False
        ),

        sa.Column(
            "lesson_date",
            sa.Date(),
            nullable=True
        ),

        sa.Column(
            "class_name",
            sa.String(length=100),
            nullable=False
        ),

        sa.Column(
            "number_in_class",
            sa.Integer(),
            nullable=True
        ),

        sa.Column(
            "average_age",
            sa.Integer(),
            nullable=True
        ),

        sa.Column(
            "subject",
            sa.String(length=150),
            nullable=False
        ),

        sa.Column(
            "lesson_topic",
            sa.String(length=255),
            nullable=False
        ),

        sa.Column(
            "unit_topic",
            sa.Text(),
            nullable=True
        ),

        sa.Column(
            "start_time",
            sa.String(length=20),
            nullable=True
        ),

        sa.Column(
            "end_time",
            sa.String(length=20),
            nullable=True
        ),

        sa.Column(
            "duration_minutes",
            sa.Integer(),
            nullable=True
        ),

        sa.Column(
            "learning_materials",
            sa.Text(),
            nullable=True
        ),

        sa.Column(
            "curriculum",
            sa.Text(),
            nullable=True
        ),

        sa.Column(
            "examination_relevance",
            sa.String(length=30),
            nullable=True
        ),

        sa.Column(
            "generated_content",
            sa.Text(),
            nullable=True
        ),

        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="CASCADE"
        ),

        sa.PrimaryKeyConstraint("id")
    )

    # ----------------------------------------------------------
    # USER INDEX
    # ----------------------------------------------------------
    with op.batch_alter_table(
        "lesson_plan",
        schema=None
    ) as batch_op:

        batch_op.create_index(
            batch_op.f("ix_lesson_plan_user_id"),
            ["user_id"],
            unique=False
        )


def downgrade():
    # ----------------------------------------------------------
    # REMOVE LESSON PLAN TABLE
    # ----------------------------------------------------------
    with op.batch_alter_table(
        "lesson_plan",
        schema=None
    ) as batch_op:

        batch_op.drop_index(
            batch_op.f("ix_lesson_plan_user_id")
        )

    op.drop_table("lesson_plan")