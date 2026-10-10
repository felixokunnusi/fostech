"""Fix student enrollment uniqueness across class groups.

Revision ID: 90f6436b767c
Revises: 572cebf3b920
"""

from alembic import op
import sqlalchemy as sa


revision = "90f6436b767c"
down_revision = "572cebf3b920"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "uq_student_subject_enrollment_context"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Stop without changing data if the new uniqueness rule would fail.
    duplicates = bind.execute(
        sa.text(
            """
            SELECT
                student_id,
                school_id,
                academic_session_id,
                class_id,
                subject_id,
                COUNT(*) AS duplicate_count
            FROM student_subject_enrollment
            GROUP BY
                student_id,
                school_id,
                academic_session_id,
                class_id,
                subject_id
            HAVING COUNT(*) > 1
            LIMIT 10
            """
        )
    ).fetchall()

    if duplicates:
        examples = "; ".join(
            f"student={row[0]}, school={row[1]}, "
            f"session={row[2]}, class={row[3]}, "
            f"subject={row[4]}, count={row[5]}"
            for row in duplicates
        )
        raise RuntimeError(
            "Cannot update enrollment uniqueness because duplicate "
            "enrollments exist. Review and reconcile them manually. "
            f"Examples: {examples}"
        )

    constraints = inspector.get_unique_constraints(
        "student_subject_enrollment"
    )

    existing = next(
        (
            constraint
            for constraint in constraints
            if constraint["name"] == CONSTRAINT_NAME
        ),
        None,
    )

    if existing is None:
        raise RuntimeError(
            f"Expected unique constraint {CONSTRAINT_NAME!r} "
            "was not found on student_subject_enrollment."
        )

    old_columns = existing.get("column_names") or []
    expected_old_columns = [
        "student_id",
        "school_id",
        "academic_session_id",
        "class_id",
        "class_group_id",
        "subject_id",
    ]

    if old_columns != expected_old_columns:
        raise RuntimeError(
            "The existing enrollment uniqueness constraint has an "
            f"unexpected definition: {old_columns!r}"
        )

    # SQLite requires batch table recreation for constraint changes.
    with op.batch_alter_table(
        "student_subject_enrollment",
        recreate="auto",
    ) as batch_op:
        batch_op.drop_constraint(
            CONSTRAINT_NAME,
            type_="unique",
        )
        batch_op.create_unique_constraint(
            CONSTRAINT_NAME,
            [
                "student_id",
                "school_id",
                "academic_session_id",
                "class_id",
                "subject_id",
            ],
        )


def downgrade():
    bind = op.get_bind()

    # The original constraint included class_group_id. Before restoring
    # it, ensure existing records do not conflict with that rule.
    duplicates = bind.execute(
        sa.text(
            """
            SELECT
                student_id,
                school_id,
                academic_session_id,
                class_id,
                class_group_id,
                subject_id,
                COUNT(*) AS duplicate_count
            FROM student_subject_enrollment
            GROUP BY
                student_id,
                school_id,
                academic_session_id,
                class_id,
                class_group_id,
                subject_id
            HAVING COUNT(*) > 1
            LIMIT 10
            """
        )
    ).fetchall()

    if duplicates:
        raise RuntimeError(
            "Cannot restore the previous enrollment constraint because "
            "duplicate records exist under the previous rule. "
            "Reconcile them manually before downgrading."
        )

    with op.batch_alter_table(
        "student_subject_enrollment",
        recreate="auto",
    ) as batch_op:
        batch_op.drop_constraint(
            CONSTRAINT_NAME,
            type_="unique",
        )
        batch_op.create_unique_constraint(
            CONSTRAINT_NAME,
            [
                "student_id",
                "school_id",
                "academic_session_id",
                "class_id",
                "class_group_id",
                "subject_id",
            ],
        )
