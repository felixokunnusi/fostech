import csv
import io
import re
from typing import Any, Dict, List, Set, Tuple

from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models.quiz import Question, Choice


# CSV schema
REQUIRED_COLUMNS = {
    "source",
    "level",
    "mode",
    "question_text",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_option",
    "explanation",
    "question_type",
}

OPTION_COLUMNS = [
    "option_a",
    "option_b",
    "option_c",
    "option_d",
]

VALID_MODES = {"trial", "exam"}
VALID_CORRECT = {"A", "B", "C", "D"}

# Number of questions inserted before flushing the session.
# Increase carefully if uploads are very large.
BATCH_SIZE = 250


def _norm_text(value: str) -> str:
    """
    Normalize text for duplicate comparison.

    This makes duplicate checking:
    - case-insensitive
    - insensitive to leading/trailing spaces
    - insensitive to repeated internal spaces
    """
    value = (value or "").strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


def _get_cell(row: Dict[str, str], key: str) -> str:
    """
    Safely retrieve and trim a CSV cell.
    """
    return (row.get(key) or "").strip()


def _validate_row(
    row: Dict[str, str],
) -> Tuple[bool, List[str]]:
    """
    Validate one CSV row.
    """
    errors: List[str] = []

    level = _get_cell(row, "level")
    question_type = _get_cell(row, "question_type")
    question_text = _get_cell(row, "question_text")
    mode = _get_cell(row, "mode").lower()
    correct_option = _get_cell(
        row,
        "correct_option",
    ).upper()

    if not level:
        errors.append("Missing level")

    if not question_type:
        errors.append("Missing question_type")

    if not question_text:
        errors.append("Missing question_text")

    if mode not in VALID_MODES:
        errors.append(
            "mode must be 'trial' or 'exam'"
        )

    for column in OPTION_COLUMNS:
        if not _get_cell(row, column):
            errors.append(f"Missing {column}")

    if correct_option not in VALID_CORRECT:
        errors.append(
            "correct_option must be one of A, B, C, D"
        )

    return len(errors) == 0, errors


def _make_duplicate_key(
    band: str,
    question_type: str,
    question_text: str,
) -> Tuple[str, str, str]:
    """
    Build the duplicate-check key.

    This preserves the existing duplicate rule:
    band + question_type + normalized question text.
    """
    return (
        band,
        question_type,
        _norm_text(question_text),
    )


def _load_existing_duplicate_keys(
    band_type_pairs: Set[Tuple[str, str]],
) -> Set[Tuple[str, str, str]]:
    """
    Load existing database questions only for the band and
    question-type combinations present in the uploaded CSV.

    This replaces running a separate database query for every row.
    """
    if not band_type_pairs:
        return set()

    filters = [
        (
            (Question.band == band)
            & (Question.question_type == question_type)
        )
        for band, question_type in band_type_pairs
    ]

    existing_rows = (
        db.session.query(
            Question.band,
            Question.question_type,
            Question.text,
        )
        .filter(or_(*filters))
        .all()
    )

    return {
        _make_duplicate_key(
            band=row.band,
            question_type=row.question_type,
            question_text=row.text,
        )
        for row in existing_rows
    }


def import_questions_from_csv_file(
    file_storage,
) -> Dict[str, Any]:
    """
    Import questions from an uploaded CSV file.

    Expected columns:
      source
      level
      mode
      question_text
      option_a
      option_b
      option_c
      option_d
      correct_option
      explanation
      question_type

    Field mapping:
      level         -> Question.band
      question_text -> Question.text
      question_type -> Question.question_type
      explanation   -> Question.explanation

    Duplicate rule:
      (
          Question.band,
          Question.question_type,
          normalized Question.text,
      )

    The optimized duplicate check prevents duplicates:
      1. Already existing in the database
      2. Repeated within the same uploaded CSV file
    """
    summary: Dict[str, Any] = {
        "inserted_questions": 0,
        "skipped_duplicates": 0,
        "updated_questions": 0,
        "inserted_choices": 0,
        "rows_total": 0,
        "errors": [],
        "warnings": [],
    }

    try:
        raw = file_storage.read()

        try:
            # Handles standard UTF-8 and UTF-8 files with BOM.
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            # Fallback for CSV files exported with older encodings.
            text = raw.decode("latin-1")

        stream = io.StringIO(text)
        reader = csv.DictReader(stream)

        if not reader.fieldnames:
            summary["errors"].append(
                {
                    "row": 0,
                    "message": "CSV has no header row.",
                }
            )
            return summary

        # Normalize the CSV headers.
        reader.fieldnames = [
            header.strip().lstrip("\ufeff")
            for header in reader.fieldnames
            if header
        ]

        headers = set(reader.fieldnames)
        missing = REQUIRED_COLUMNS - headers

        if missing:
            summary["errors"].append(
                {
                    "row": 0,
                    "message": (
                        "Missing required columns: "
                        f"{', '.join(sorted(missing))}"
                    ),
                }
            )
            return summary

        # First pass:
        # Validate rows and prepare their values in memory.
        prepared_rows: List[Dict[str, Any]] = []
        band_type_pairs: Set[Tuple[str, str]] = set()

        for row_number, row in enumerate(
            reader,
            start=2,
        ):
            summary["rows_total"] += 1

            is_valid, row_errors = _validate_row(row)

            if not is_valid:
                summary["errors"].append(
                    {
                        "row": row_number,
                        "message": "; ".join(row_errors),
                        "data": {
                            "level": _get_cell(
                                row,
                                "level",
                            ),
                            "question_type": _get_cell(
                                row,
                                "question_type",
                            ),
                            "question_text": _get_cell(
                                row,
                                "question_text",
                            )[:120],
                        },
                    }
                )
                continue

            band = _get_cell(row, "level")
            question_type = _get_cell(
                row,
                "question_type",
            )
            question_text = _get_cell(
                row,
                "question_text",
            )
            explanation = _get_cell(
                row,
                "explanation",
            )
            correct_option = _get_cell(
                row,
                "correct_option",
            ).upper()

            options = {
                "A": _get_cell(row, "option_a"),
                "B": _get_cell(row, "option_b"),
                "C": _get_cell(row, "option_c"),
                "D": _get_cell(row, "option_d"),
            }

            prepared_rows.append(
                {
                    "row_number": row_number,
                    "band": band,
                    "question_type": question_type,
                    "question_text": question_text,
                    "explanation": explanation,
                    "correct_option": correct_option,
                    "options": options,
                }
            )

            band_type_pairs.add(
                (band, question_type)
            )

        # Load relevant existing questions with one database query.
        duplicate_keys = _load_existing_duplicate_keys(
            band_type_pairs
        )

        # Pending questions and their choice information.
        pending: List[
            Tuple[
                Question,
                Dict[str, str],
                str,
            ]
        ] = []

        def flush_pending() -> None:
            """
            Flush one batch of questions, obtain their IDs,
            and add their choices.
            """
            if not pending:
                return

            questions = [
                question
                for question, _, _ in pending
            ]

            db.session.add_all(questions)

            # One flush per batch instead of one flush per question.
            db.session.flush()

            choices: List[Choice] = []

            for question, options, correct_label in pending:
                for label in VALID_CORRECT:
                    choices.append(
                        Choice(
                            question_id=question.id,
                            text=options[label],
                            is_correct=(
                                label == correct_label
                            ),
                        )
                    )

            db.session.add_all(choices)
            pending.clear()

        # Second pass:
        # Check duplicates in memory and prepare batch inserts.
        for prepared in prepared_rows:
            duplicate_key = _make_duplicate_key(
                band=prepared["band"],
                question_type=prepared[
                    "question_type"
                ],
                question_text=prepared[
                    "question_text"
                ],
            )

            if duplicate_key in duplicate_keys:
                summary["skipped_duplicates"] += 1
                continue

            question = Question(
                band=prepared["band"],
                question_type=prepared[
                    "question_type"
                ],
                text=prepared["question_text"],
                explanation=(
                    prepared["explanation"]
                    if prepared["explanation"]
                    else None
                ),
            )

            pending.append(
                (
                    question,
                    prepared["options"],
                    prepared["correct_option"],
                )
            )

            summary["inserted_questions"] += 1
            summary["inserted_choices"] += 4

            # Add immediately so duplicate rows later in the same
            # uploaded CSV will also be skipped.
            duplicate_keys.add(duplicate_key)

            if len(pending) >= BATCH_SIZE:
                flush_pending()

        # Insert the final incomplete batch.
        flush_pending()

        db.session.commit()

    except SQLAlchemyError as error:
        db.session.rollback()

        # No rows were permanently inserted because the
        # transaction was rolled back.
        summary["inserted_questions"] = 0
        summary["inserted_choices"] = 0

        summary["errors"].append(
            {
                "row": None,
                "message": (
                    "Database error: "
                    f"{str(error)}"
                ),
            }
        )

    except (csv.Error, UnicodeError) as error:
        db.session.rollback()

        summary["inserted_questions"] = 0
        summary["inserted_choices"] = 0

        summary["errors"].append(
            {
                "row": None,
                "message": (
                    "CSV reading error: "
                    f"{str(error)}"
                ),
            }
        )

    except Exception as error:
        db.session.rollback()

        summary["inserted_questions"] = 0
        summary["inserted_choices"] = 0

        summary["errors"].append(
            {
                "row": None,
                "message": (
                    "Unexpected import error: "
                    f"{str(error)}"
                ),
            }
        )

    return summary