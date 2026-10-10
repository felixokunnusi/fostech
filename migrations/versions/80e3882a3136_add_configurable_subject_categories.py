"""add configurable subject categories

Revision ID: 80e3882a3136
Revises: 7bb4609a4424
Create Date: 2026-09-26 18:29:56.783668
"""

from alembic import op
import sqlalchemy as sa


revision = "80e3882a3136"
down_revision = "7bb4609a4424"
branch_labels = None
depends_on = None


def _inspector():
    """Return an inspector for the current database connection."""
    return sa.inspect(op.get_bind())


def _table_exists(table_name):
    return _inspector().has_table(table_name)


def _column_exists(table_name, column_name):
    inspector = _inspector()

    if not inspector.has_table(table_name):
        return False

    return any(
        column["name"] == column_name
        for column in inspector.get_columns(table_name)
    )


def _index_exists(table_name, index_name):
    inspector = _inspector()

    if not inspector.has_table(table_name):
        return False

    return any(
        index["name"] == index_name
        for index in inspector.get_indexes(table_name)
    )


def _foreign_key_exists(table_name, constraint_name):
    inspector = _inspector()

    if not inspector.has_table(table_name):
        return False

    return any(
        foreign_key.get("name") == constraint_name
        for foreign_key in inspector.get_foreign_keys(table_name)
    )


def _add_foreign_key_if_missing(
    table_name,
    constraint_name,
    referred_table,
    local_column,
    referred_column,
    ondelete,
):
    if _foreign_key_exists(table_name, constraint_name):
        return

    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.create_foreign_key(
            constraint_name,
            referred_table,
            [local_column],
            [referred_column],
            ondelete=ondelete,
        )


def upgrade():
    # 1. Create the category table if it is absent.
    if not _table_exists("subject_category"):
        op.create_table(
            "subject_category",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["school_id"],
                ["school.id"],
                name="fk_subject_category_school_id",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    # 2. Create the category school index if absent.
    if not _index_exists(
        "subject_category",
        "ix_subject_category_school_id",
    ):
        op.create_index(
            "ix_subject_category_school_id",
            "subject_category",
            ["school_id"],
            unique=False,
        )

    # 3. Add class_group.category_id if absent.
    if not _column_exists("class_group", "category_id"):
        with op.batch_alter_table("class_group", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("category_id", sa.Integer(), nullable=True)
            )

    # 4. Create the class-group category index if absent.
    if not _index_exists(
        "class_group",
        "ix_class_group_category_id",
    ):
        with op.batch_alter_table("class_group", schema=None) as batch_op:
            batch_op.create_index(
                "ix_class_group_category_id",
                ["category_id"],
                unique=False,
            )

    # 5. Add the class-group foreign key if absent.
    _add_foreign_key_if_missing(
        "class_group",
        "fk_class_group_category_id",
        "subject_category",
        "category_id",
        "id",
        "SET NULL",
    )

    # 6. Add school_subject.category_id if absent.
    if not _column_exists("school_subject", "category_id"):
        with op.batch_alter_table("school_subject", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("category_id", sa.Integer(), nullable=True)
            )

    # 7. Create the school-subject category index if absent.
    if not _index_exists(
        "school_subject",
        "ix_school_subject_category_id",
    ):
        with op.batch_alter_table("school_subject", schema=None) as batch_op:
            batch_op.create_index(
                "ix_school_subject_category_id",
                ["category_id"],
                unique=False,
            )

    # 8. Add the school-subject foreign key if absent.
    _add_foreign_key_if_missing(
        "school_subject",
        "fk_school_subject_category_id",
        "subject_category",
        "category_id",
        "id",
        "SET NULL",
    )


def downgrade():
    # Remove the school-subject category relationship if present.
    if _table_exists("school_subject"):
        if _foreign_key_exists(
            "school_subject",
            "fk_school_subject_category_id",
        ):
            with op.batch_alter_table(
                "school_subject",
                schema=None,
            ) as batch_op:
                batch_op.drop_constraint(
                    "fk_school_subject_category_id",
                    type_="foreignkey",
                )

        if _index_exists(
            "school_subject",
            "ix_school_subject_category_id",
        ):
            with op.batch_alter_table(
                "school_subject",
                schema=None,
            ) as batch_op:
                batch_op.drop_index("ix_school_subject_category_id")

        if _column_exists("school_subject", "category_id"):
            with op.batch_alter_table(
                "school_subject",
                schema=None,
            ) as batch_op:
                batch_op.drop_column("category_id")

    # Remove the class-group category relationship if present.
    if _table_exists("class_group"):
        if _foreign_key_exists(
            "class_group",
            "fk_class_group_category_id",
        ):
            with op.batch_alter_table(
                "class_group",
                schema=None,
            ) as batch_op:
                batch_op.drop_constraint(
                    "fk_class_group_category_id",
                    type_="foreignkey",
                )

        if _index_exists(
            "class_group",
            "ix_class_group_category_id",
        ):
            with op.batch_alter_table(
                "class_group",
                schema=None,
            ) as batch_op:
                batch_op.drop_index("ix_class_group_category_id")

        if _column_exists("class_group", "category_id"):
            with op.batch_alter_table(
                "class_group",
                schema=None,
            ) as batch_op:
                batch_op.drop_column("category_id")

    # Remove the category table and its index if present.
    if _table_exists("subject_category"):
        if _index_exists(
            "subject_category",
            "ix_subject_category_school_id",
        ):
            op.drop_index(
                "ix_subject_category_school_id",
                table_name="subject_category",
            )

        op.drop_table("subject_category")
