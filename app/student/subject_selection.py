from collections import defaultdict

from app.models.category_rule import CategoryRule
from app.models.category_subject_config import CategorySubjectConfig
from app.models.subject_selection_rule import SubjectSelectionRule
from app.models.subject_category import SubjectCategory


def validate_subject_selection(
    school_id,
    subject_ids,
    stream_category_id,
):
    """
    Validate a student's proposed subject selection against:

    1. School-wide minimum/maximum subjects.
    2. The student's stream/category.
    3. Core subjects.
    4. Trade subjects.
    5. Stream-specific subjects.
    6. Required subjects.
    7. Category minimum/maximum rules.

    Category availability:

        Science:
            Core + Trade + Science

        Business:
            Core + Trade + Business

        Humanities:
            Core + Trade + Humanities + Nigerian Language
    """

    # ------------------------------------------------------------------
    # Convert subject IDs safely.
    # ------------------------------------------------------------------

    try:
        subject_ids = {
            int(subject_id)
            for subject_id in subject_ids
        }

    except (TypeError, ValueError):
        return {
            "valid": False,
            "errors": ["Invalid subject selection."],
            "selected_subjects": [],
            "selected_count": 0,
            "categories": {},
        }

    # ------------------------------------------------------------------
    # Validate stream category.
    # ------------------------------------------------------------------

    stream_category = (
        SubjectCategory.query
        .filter_by(
            id=stream_category_id,
            school_id=school_id,
            active=True,
        )
        .first()
    )

    if stream_category is None:
        return {
            "valid": False,
            "errors": [
                "The student's class stream has not been "
                "configured correctly."
            ],
            "selected_subjects": [],
            "selected_count": len(subject_ids),
            "categories": {},
        }

    # ------------------------------------------------------------------
    # School-wide rule.
    # ------------------------------------------------------------------

    overall_rule = (
        SubjectSelectionRule.query
        .filter_by(
            school_id=school_id,
            active=True,
        )
        .first()
    )

    if overall_rule is None:
        return {
            "valid": False,
            "errors": [
                "No active school-wide subject selection rule "
                "has been configured."
            ],
            "selected_subjects": [],
            "selected_count": len(subject_ids),
            "categories": {},
        }

    selected_count = len(subject_ids)
    errors = []

    if selected_count < overall_rule.minimum_subjects:
        errors.append(
            f"You must select at least "
            f"{overall_rule.minimum_subjects} subjects."
        )

    if selected_count > overall_rule.maximum_subjects:
        errors.append(
            f"You cannot select more than "
            f"{overall_rule.maximum_subjects} subjects."
        )

    # ------------------------------------------------------------------
    # Load active categories.
    # ------------------------------------------------------------------

    categories = (
        SubjectCategory.query
        .filter_by(
            school_id=school_id,
            active=True,
        )
        .all()
    )

    category_by_name = {
        category.name.strip().casefold(): category
        for category in categories
    }

    core_category = category_by_name.get("core")
    trade_category = category_by_name.get("trade")
    nigerian_language_category = category_by_name.get(
        "nigerian language"
    )

    # ------------------------------------------------------------------
    # Determine categories available to this student.
    # ------------------------------------------------------------------

    allowed_category_ids = set()

    if core_category:
        allowed_category_ids.add(core_category.id)

    if trade_category:
        allowed_category_ids.add(trade_category.id)

    # The student's stream category.
    allowed_category_ids.add(stream_category.id)

    # Humanities students also get Nigerian Language.
    if (
        stream_category.name.strip().casefold()
        == "humanities"
        and nigerian_language_category
    ):
        allowed_category_ids.add(
            nigerian_language_category.id
        )

    # ------------------------------------------------------------------
    # Load configured subjects.
    # ------------------------------------------------------------------

    subject_configs = (
        CategorySubjectConfig.query
        .filter_by(
            school_id=school_id,
            active=True,
        )
        .all()
    )

    config_by_subject_id = {
        config.subject_id: config
        for config in subject_configs
    }

    # ------------------------------------------------------------------
    # Reject subjects outside the student's permitted categories.
    # ------------------------------------------------------------------

    for subject_id in subject_ids:

        config = config_by_subject_id.get(subject_id)

        if config is None:
            errors.append(
                "One or more selected subjects are not "
                "available for this school's subject selection."
            )
            continue

        if config.category_id not in allowed_category_ids:
            errors.append(
                f"{config.subject.name} is not available "
                f"for {stream_category.name} students."
            )

        if not config.selectable and not config.required:
            errors.append(
                f"{config.subject.name} cannot be selected."
            )

    # ------------------------------------------------------------------
    # Required subjects.
    #
    # Required subjects are only enforced from categories that apply
    # to this student's stream.
    # ------------------------------------------------------------------

    required_subject_ids = {
        config.subject_id
        for config in subject_configs
        if (
            config.required
            and config.category_id in allowed_category_ids
        )
    }

    missing_required = (
        required_subject_ids - subject_ids
    )

    for subject_id in missing_required:

        config = config_by_subject_id.get(subject_id)

        if config:
            errors.append(
                f"{config.subject.name} is required."
            )

    # ------------------------------------------------------------------
    # Group selected subjects by category.
    # ------------------------------------------------------------------

    selected_by_category = defaultdict(list)

    for subject_id in subject_ids:

        config = config_by_subject_id.get(subject_id)

        if config is None:
            continue

        selected_by_category[
            config.category_id
        ].append(config)

    # ------------------------------------------------------------------
    # Apply category rules only to categories relevant to this student.
    # ------------------------------------------------------------------

    category_rules = (
        CategoryRule.query
        .filter_by(
            school_id=school_id,
            active=True,
        )
        .all()
    )

    for rule in category_rules:

        if rule.category_id not in allowed_category_ids:
            continue

        category = rule.category

        selected_in_category = selected_by_category.get(
            category.id,
            [],
        )

        category_count = len(
            selected_in_category
        )

        if (
            rule.required
            and category_count == 0
        ):
            errors.append(
                f"{category.name} is required."
            )

        if category_count < rule.minimum_subjects:
            errors.append(
                f"{category.name} requires at least "
                f"{rule.minimum_subjects} subject(s)."
            )

        if (
            rule.maximum_subjects is not None
            and category_count > rule.maximum_subjects
        ):
            errors.append(
                f"{category.name} allows a maximum of "
                f"{rule.maximum_subjects} subject(s)."
            )

    # ------------------------------------------------------------------
    # Return validation result.
    # ------------------------------------------------------------------

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "selected_subjects": [
            config.subject
            for config in subject_configs
            if config.subject_id in subject_ids
        ],
        "selected_count": selected_count,
        "categories": dict(selected_by_category),
        "stream_category": stream_category,
        "allowed_category_ids": allowed_category_ids,
    }