"""
FCT-EMIS Lesson Plan Renderer

Converts a saved LessonPlan and its structured AI-generated content
into presentation-ready data for the FCT-EMIS lesson-plan template.

This module handles presentation preparation only.
It does not generate lesson content and does not modify the database.
"""


STAGE_DEFINITIONS = (
    ("prior_ideas", "STEP I", "IDENTIFICATION OF PRIOR IDEAS"),
    ("exploration", "STEP II", "EXPLORATION"),
    ("discussion", "STEP III", "DISCUSSION"),
    ("application", "STEP IV", "APPLICATION"),
    ("evaluation", "STEP V", "EVALUATION"),
)


def _safe_stage(generated_content, key):
    """Return a valid stage dictionary even if a field is missing."""
    stage = generated_content.get(key, {})

    if not isinstance(stage, dict):
        stage = {}

    return {
        "mode": stage.get("mode", ""),
        "teacher_activities": stage.get("teacher_activities", ""),
        "student_activities": stage.get("student_activities", ""),
    }


def build_fct_emis_view_model(lesson_plan, generated_content):
    """
    Build the data required by the FCT-EMIS presentation template.

    Parameters
    ----------
    lesson_plan:
        Saved LessonPlan database object.

    generated_content:
        Parsed structured AI-generated lesson content.

    Returns
    -------
    dict
        Presentation-ready FCT-EMIS lesson-plan data.
    """

    generated_content = generated_content or {}

    stages = []

    for key, step_number, title in STAGE_DEFINITIONS:
        stage = _safe_stage(generated_content, key)

        stages.append(
            {
                "key": key,
                "step_number": step_number,
                "title": title,
                **stage,
            }
        )

    return {
        "header": {
            "organisation": "MODERN TEACHING APPROACH",
            "system": "",
            "document_title": "LESSON PLAN",
        },
        "lesson_information": {
            "date": lesson_plan.lesson_date,
            "class_name": lesson_plan.class_name,
            "number_in_class": lesson_plan.number_in_class,
            "average_age": lesson_plan.average_age,
            "subject": lesson_plan.subject,
            "lesson_topic": lesson_plan.lesson_topic,
            "time": _format_time(
                lesson_plan.start_time,
                lesson_plan.end_time,
            ),
            "unit_topic": lesson_plan.unit_topic,
            "duration_minutes": lesson_plan.duration_minutes,
            "learning_materials": lesson_plan.learning_materials,
        },
        "lesson_objectives": generated_content.get(
            "lesson_objectives",
            [],
        ),
        "stages": stages,
        "references": generated_content.get(
            "references",
            [],
        ),
        "home_task": generated_content.get(
            "home_task",
            "",
        ),
        "remarks": {
            "hod_vp_academics": {
                "remark": "",
                "name": "",
                "date": "",
            },
            "inspector_evaluator": {
                "remark": "",
                "name": "",
                "date": "",
            },
        },
    }


def _format_time(start_time, end_time):
    """Format lesson start/end times for the FCT-EMIS document."""

    if start_time and end_time:
        return f"{start_time} - {end_time}"

    if start_time:
        return start_time

    if end_time:
        return end_time

    return ""