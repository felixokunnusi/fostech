"""add configurable subject categories

Revision ID: 80e3882a3136
Revises: 7bb4609a4424
Create Date: 2026-09-26 18:29:56.783668

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "80e3882a3136"
down_revision = "7bb4609a4424"
branch_labels = None
depends_on = None


def _table_exists(table_name):
    """Return True if the SQLite table already exists."""
    bind = op.get_bind()

    result = bind.execute(
        sa.text(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = :table_name
            """
        ),
        {"table_name": table_name},
    )

    return result.first() is not None


def _column_exists(table_name, column_name):
    """Return True if a column already exists in a SQLite table."""
    bind = op.get_bind()

    result = bind.execute(
        sa.text(
            f'PRAGMA table_info("{table_name}")'
        )
    )

    columns = result.fetchall()

    return any(row[1] == column_name for row in columns)


def _index_exists(index_name):
    """Return True if the SQLite index already exists."""
    bind = op.get_bind()

    result = bind.execute(
        sa.text(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index'
              AND name = :index_name
            """
        ),
        {"index_name": index_name},
    )

    return result.first() is not None


def upgrade():
    # ------------------------------------------------------------------
    # 1. Create subject_category table if it does not already exist.
    #
    # The table may already exist because the previous migration attempt
    # succeeded in creating it before failing later in the migration.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # 2. Create subject_category school index if necessary.
    # ------------------------------------------------------------------
    if not _index_exists("ix_subject_category_school_id"):
        op.create_index(
            "ix_subject_category_school_id",
            "subject_category",
            ["school_id"],
            unique=False,
        )

    # ------------------------------------------------------------------
    # 3. Add category_id to class_group if necessary.
    # ------------------------------------------------------------------
    if not _column_exists("class_group", "category_id"):
        with op.batch_alter_table("class_group", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "category_id",
                    sa.Integer(),
                    nullable=True,
                )
            )

    # ------------------------------------------------------------------
    # 4. Create class_group category index if necessary.
    # ------------------------------------------------------------------
    if not _index_exists("ix_class_group_category_id"):
        with op.batch_alter_table("class_group", schema=None) as batch_op:
            batch_op.create_index(
                "ix_class_group_category_id",
                ["category_id"],
                unique=False,
            )

    # ------------------------------------------------------------------
    # 5. Add class_group -> subject_category foreign key.
    #
    # We use batch mode because this is SQLite.
    # ------------------------------------------------------------------
    with op.batch_alter_table("class_group", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_class_group_category_id",
            "subject_category",
            ["category_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # ------------------------------------------------------------------
    # 6. Add category_id to school_subject if necessary.
    # ------------------------------------------------------------------
    if not _column_exists("school_subject", "category_id"):
        with op.batch_alter_table("school_subject", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "category_id",
                    sa.Integer(),
                    nullable=True,
                )
            )

    # ------------------------------------------------------------------
    # 7. Create school_subject category index if necessary.
    # ------------------------------------------------------------------
    if not _index_exists("ix_school_subject_category_id"):
        with op.batch_alter_table("school_subject", schema=None) as batch_op:
            batch_op.create_index(
                "ix_school_subject_category_id",
                ["category_id"],
                unique=False,
            )

    # ------------------------------------------------------------------
    # 8. Add school_subject -> subject_category foreign key.
    # ------------------------------------------------------------------
    with op.batch_alter_table("school_subject", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_school_subject_category_id",
            "subject_category",
            ["category_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    # ------------------------------------------------------------------
    # Remove school_subject foreign key, index and column.
    # ------------------------------------------------------------------
    with op.batch_alter_table("school_subject", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_school_subject_category_id",
            type_="foreignkey",
        )

        batch_op.drop_index(
            "ix_school_subject_category_id",
        )

        batch_op.drop_column("category_id")

    # ------------------------------------------------------------------
    # Remove class_group foreign key, index and column.
    # ------------------------------------------------------------------
    with op.batch_alter_table("class_group", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_class_group_category_id",
            type_="foreignkey",
        )

        batch_op.drop_index(
            "ix_class_group_category_id",
        )

        batch_op.drop_column("category_id")

    # ------------------------------------------------------------------
    # Remove subject_category index and table.
    # ------------------------------------------------------------------
    op.drop_index(
        "ix_subject_category_school_id",
        table_name="subject_category",
    )

    op.drop_table("subject_category")