"""add category subject configuration

Revision ID: bc042cbe55e5
Revises: 80e3882a3136
Create Date: 2026-09-29 14:11:10.239341

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bc042cbe55e5"
down_revision = "80e3882a3136"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "category_rule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("minimum_subjects", sa.Integer(), nullable=False),
        sa.Column("maximum_subjects", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["school.id"],
            name="fk_category_rule_school_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["subject_category.id"],
            name="fk_category_rule_category_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_category_rule_school_id",
        "category_rule",
        ["school_id"],
        unique=False,
    )

    op.create_index(
        "ix_category_rule_category_id",
        "category_rule",
        ["category_id"],
        unique=False,
    )

    op.create_table(
        "category_subject_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("selectable", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["school.id"],
            name="fk_category_subject_config_school_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["subject_category.id"],
            name="fk_category_subject_config_category_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["school_subject.id"],
            name="fk_category_subject_config_subject_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_category_subject_config_school_id",
        "category_subject_config",
        ["school_id"],
        unique=False,
    )

    op.create_index(
        "ix_category_subject_config_category_id",
        "category_subject_config",
        ["category_id"],
        unique=False,
    )

    op.create_index(
        "ix_category_subject_config_subject_id",
        "category_subject_config",
        ["subject_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_category_subject_config_subject_id",
        table_name="category_subject_config",
    )

    op.drop_index(
        "ix_category_subject_config_category_id",
        table_name="category_subject_config",
    )

    op.drop_index(
        "ix_category_subject_config_school_id",
        table_name="category_subject_config",
    )

    op.drop_table("category_subject_config")

    op.drop_index(
        "ix_category_rule_category_id",
        table_name="category_rule",
    )

    op.drop_index(
        "ix_category_rule_school_id",
        table_name="category_rule",
    )

    op.drop_table("category_rule")