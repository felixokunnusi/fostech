import csv
import io
import re
from typing import Dict, Any, List, Tuple

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models.quiz import Question, Choice


# New CSV schema (matches what you asked for)
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

OPTION_COLUMNS = ["option_a", "option_b", "option_c", "option_d"]
VALID_MODES = {"trial", "exam"}
VALID_CORRECT = {"A", "B", "C", "D"}


def _norm_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _get_cell(row: Dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def _validate_row(row: Dict[str, str]) -> Tuple[bool, List[str]]:
    errs: List[str] = []

    level = _get_cell(row, "level")
    qtype = _get_cell(row, "question_type")
    qtext = _get_cell(row, "question_text")
    mode = _get_cell(row, "mode").lower()
    correct = _get_cell(row, "correct_option").upper()

    if not level:
        errs.append("Missing level")
    if not qtype:
        errs.append("Missing question_type")
    if not qtext:
        errs.append("Missing question_text")

    if mode not in VALID_MODES:
        errs.append("mode must be 'trial' or 'exam'")

    for col in OPTION_COLUMNS:
        if not _get_cell(row, col):
            errs.append(f"Missing {col}")

    if correct not in VALID_CORRECT:
        errs.append("correct_option must be one of A, B, C, D")

    return (len(errs) == 0), errs


def import_questions_from_csv_file(file_storage) -> Dict[str, Any]:
    """
    Expected columns:
      source, level, mode, question_text, option_a, option_b, option_c, option_d,
      correct_option (A/B/C/D), explanation, question_type

    Mapping:
      level -> Question.band
      question_text -> Question.text
      question_type -> Question.question_type
      explanation -> Question.explanation

    Dedupes by: (band, question_type, normalized(question_text))
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

    raw = file_storage.read()
    try:
        text = raw.decode("utf-8-sig")  # handles BOM
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    stream = io.StringIO(text)
    reader = csv.DictReader(stream)

    if not reader.fieldnames:
        summary["errors"].append({"row": 0, "message": "CSV has no header row."})
        return summary

    # Normalize headers: strip spaces + remove BOM if it snuck into first header
    reader.fieldnames = [h.strip().lstrip("\ufeff") for h in reader.fieldnames if h]
    headers = set(reader.fieldnames)

    missing = REQUIRED_COLUMNS - headers
    if missing:
        summary["errors"].append({
            "row": 0,
            "message": f"Missing required columns: {', '.join(sorted(missing))}"
        })
        return summary

    try:
        for idx, row in enumerate(reader, start=2):
            summary["rows_total"] += 1

            ok, row_errs = _validate_row(row)
            if not ok:
                summary["errors"].append({
                    "row": idx,
                    "message": "; ".join(row_errs),
                    "data": {
                        "level": _get_cell(row, "level"),
                        "question_type": _get_cell(row, "question_type"),
                        "question_text": _get_cell(row, "question_text")[:120],
                    }
                })
                continue

            # Map CSV -> DB fields
            band = _get_cell(row, "level")  # ✅ level maps into Question.band
            qtype = _get_cell(row, "question_type")
            qtext = _get_cell(row, "question_text")
            explanation = _get_cell(row, "explanation")

            norm = _norm_text(qtext)

            # Dedupes by band + type + normalized text
            existing = (
                Question.query
                .filter(Question.band == band, Question.question_type == qtype)
                .all()
            )
            dup = next((q for q in existing if _norm_text(q.text) == norm), None)
            if dup:
                summary["skipped_duplicates"] += 1
                continue

            q = Question(
                band=band,
                question_type=qtype,
                text=qtext,
                explanation=explanation if explanation else None,
            )
            db.session.add(q)
            db.session.flush()

            correct_label = _get_cell(row, "correct_option").upper()

            # Map A/B/C/D to option_a/b/c/d
            opt_map = {
                "A": _get_cell(row, "option_a"),
                "B": _get_cell(row, "option_b"),
                "C": _get_cell(row, "option_c"),
                "D": _get_cell(row, "option_d"),
            }

            for label in ["A", "B", "C", "D"]:
                c = Choice(
                    question_id=q.id,
                    text=opt_map[label],
                    is_correct=(label == correct_label)
                )
                db.session.add(c)
                summary["inserted_choices"] += 1

            summary["inserted_questions"] += 1

        db.session.commit()

    except SQLAlchemyError as e:
        db.session.rollback()
        summary["errors"].append({"row": None, "message": f"Database error: {str(e)}"})

    return summary
