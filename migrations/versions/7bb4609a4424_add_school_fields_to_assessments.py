"""Add school fields to assessments

Revision ID: 7bb4609a4424
Revises: 49ef530b7669
Create Date: 2026-09-25 08:47:14.626720

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7bb4609a4424"
down_revision = "49ef530b7669"
branch_labels = None
depends_on = None


def upgrade():
    # SQLite requires explicitly named foreign-key constraints
    # when using Alembic batch_alter_table().
    with op.batch_alter_table("assessment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("school_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("academic_session_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("class_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("class_group_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("subject_id", sa.Integer(), nullable=True)
        )

        batch_op.create_index(
            batch_op.f("ix_assessment_academic_session_id"),
            ["academic_session_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_assessment_class_group_id"),
            ["class_group_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_assessment_class_id"),
            ["class_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_assessment_school_id"),
            ["school_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_assessment_subject_id"),
            ["subject_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_assessment_subject_id_school_subject",
            "school_subject",
            ["subject_id"],
            ["id"],
            ondelete="SET NULL",
        )

        batch_op.create_foreign_key(
            "fk_assessment_school_id_school",
            "school",
            ["school_id"],
            ["id"],
            ondelete="CASCADE",
        )

        batch_op.create_foreign_key(
            "fk_assessment_academic_session_id_session",
            "academic_session",
            ["academic_session_id"],
            ["id"],
            ondelete="CASCADE",
        )

        batch_op.create_foreign_key(
            "fk_assessment_class_group_id_class_group",
            "class_group",
            ["class_group_id"],
            ["id"],
            ondelete="SET NULL",
        )

        batch_op.create_foreign_key(
            "fk_assessment_class_id_school_class",
            "school_class",
            ["class_id"],
            ["id"],
            ondelete="SET NULL",
        )

def downgrade():
    with op.batch_alter_table("assessment", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_assessment_class_id_school_class",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_assessment_class_group_id_class_group",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_assessment_academic_session_id_session",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_assessment_school_id_school",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_assessment_subject_id_school_subject",
            type_="foreignkey",
        )

        batch_op.drop_index("ix_assessment_subject_id")
        batch_op.drop_index("ix_assessment_school_id")
        batch_op.drop_index("ix_assessment_class_id")
        batch_op.drop_index("ix_assessment_class_group_id")
        batch_op.drop_index("ix_assessment_academic_session_id")

        batch_op.drop_column("subject_id")
        batch_op.drop_column("class_group_id")
        batch_op.drop_column("class_id")
        batch_op.drop_column("academic_session_id")
        batch_op.drop_column("school_id")
