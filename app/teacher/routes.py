"""
Teacher Workspace Routes

Handles:
- Teacher workspace dashboard
- Lesson plan creation
- Lesson plan preview
- AI lesson-plan generation

AI-generated lesson content is stored as structured JSON text in the
LessonPlan.generated_content field.

Presentation/rendering remains separate from AI generation.
"""

import json

from flask import (
    flash,
    redirect,
    render_template,
    url_for,
)
from flask_login import current_user, login_required

from app.extensions import db
from app.models import LessonPlan
from app.teacher.ai.lesson_plan import (
    LessonPlanAIError,
    generate_lesson_plan,
)

from . import teacher_bp
from .forms import LessonPlanForm
from app.teacher.renderers.fct_emis import build_fct_emis_view_model


def teacher_has_access():
    """
    Return True when the current user has the Teacher role.
    """

    return any(
        role.role == "teacher"
        for role in current_user.roles
    )


def get_teacher_lesson_plan_or_404(lesson_plan_id):
    """
    Return a lesson plan belonging to the current teacher.

    This prevents a teacher from accessing another user's lesson plan
    simply by changing the lesson-plan ID in the URL.
    """

    return (
        LessonPlan.query
        .filter_by(
            id=lesson_plan_id,
            user_id=current_user.id,
        )
        .first_or_404()
    )


@teacher_bp.route("/")
@login_required
def dashboard():
    """
    Teacher workspace dashboard.
    """

    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    return render_template(
        "teacher/dashboard.html"
    )


@teacher_bp.route(
    "/lesson-plans/new",
    methods=["GET", "POST"],
)
@login_required
def new_lesson_plan():
    """
    Create and save a new lesson-plan draft.
    """

    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    form = LessonPlanForm()

    if form.validate_on_submit():
        lesson_plan = LessonPlan(
            user_id=current_user.id,
            format_key=form.format_key.data,
            lesson_date=form.lesson_date.data,
            class_name=form.class_name.data,
            number_in_class=form.number_in_class.data,
            average_age=form.average_age.data,
            subject=form.subject.data,
            lesson_topic=form.lesson_topic.data,
            unit_topic=form.unit_topic.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            duration_minutes=form.duration_minutes.data,
            learning_materials=form.learning_materials.data,
            curriculum=form.curriculum.data,
            examination_relevance=(
                form.examination_relevance.data or None
            ),
            status="draft",
        )

        db.session.add(lesson_plan)
        db.session.commit()

        flash(
            "Lesson plan saved successfully.",
            "success",
        )

        return redirect(
            url_for(
                "teacher.lesson_plan_preview",
                lesson_plan_id=lesson_plan.id,
            )
        )

    return render_template(
        "teacher/lesson_plan_form.html",
        form=form,
    )

@teacher_bp.route(
    "/lesson-plans/<int:lesson_plan_id>",
)
@login_required
def lesson_plan_preview(lesson_plan_id):
    """
    Display the lesson-plan preview.

    If AI-generated content exists, deserialize it from the database
    JSON string into a Python dictionary before passing it to the template.
    """

    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    lesson_plan = get_teacher_lesson_plan_or_404(
        lesson_plan_id
    )

    generated_content = None

    if lesson_plan.generated_content:
        try:
            generated_content = json.loads(
                lesson_plan.generated_content
            )
        except (TypeError, json.JSONDecodeError):
            flash(
                "The saved AI lesson content could not be read.",
                "warning",
            )

    return render_template(
        "teacher/lesson_plan_preview.html",
        lesson_plan=lesson_plan,
        generated_content=generated_content,
    )


@teacher_bp.route(
    "/lesson-plans/<int:lesson_plan_id>/generate",
    methods=["POST"],
)
@login_required
def generate_lesson_plan_ai(lesson_plan_id):
    """
    Generate structured lesson-plan content using the Teacher AI service.

    The existing lesson-plan draft is preserved if AI generation fails.
    """

    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    lesson_plan = get_teacher_lesson_plan_or_404(
        lesson_plan_id
    )

    lesson_data = {
        "format_key": lesson_plan.format_key,
        "lesson_date": (
            lesson_plan.lesson_date.isoformat()
            if lesson_plan.lesson_date
            else None
        ),
        "class_name": lesson_plan.class_name,
        "number_in_class": lesson_plan.number_in_class,
        "average_age": lesson_plan.average_age,
        "subject": lesson_plan.subject,
        "lesson_topic": lesson_plan.lesson_topic,
        "unit_topic": lesson_plan.unit_topic,
        "start_time": lesson_plan.start_time,
        "end_time": lesson_plan.end_time,
        "duration_minutes": lesson_plan.duration_minutes,
        "learning_materials": lesson_plan.learning_materials,
        "curriculum": lesson_plan.curriculum,
        "examination_relevance": (
            lesson_plan.examination_relevance
        ),
    }

    try:
        generated_content = generate_lesson_plan(
            lesson_data
        )

    except LessonPlanAIError as exc:
        db.session.rollback()

        flash(
            f"Lesson plan generation failed: {exc}",
            "danger",
        )

        return redirect(
            url_for(
                "teacher.lesson_plan_preview",
                lesson_plan_id=lesson_plan.id,
            )
        )

    except Exception:
        db.session.rollback()

        flash(
            "An unexpected error occurred while generating "
            "the lesson plan. Your draft has not been changed.",
            "danger",
        )

        return redirect(
            url_for(
                "teacher.lesson_plan_preview",
                lesson_plan_id=lesson_plan.id,
            )
        )

    lesson_plan.generated_content = json.dumps(
        generated_content,
        ensure_ascii=False,
    )

    lesson_plan.status = "generated"

    db.session.commit()

    flash(
        "Lesson plan generated successfully.",
        "success",
    )

    return redirect(
        url_for(
            "teacher.lesson_plan_preview",
            lesson_plan_id=lesson_plan.id,
        )
    )


@teacher_bp.route("/lesson-plans/<int:lesson_plan_id>/fct-emis")
@login_required
def lesson_plan_fct_emis(lesson_plan_id):
    if not teacher_has_access():
        flash("You do not have access to the Teacher workspace.", "danger")
        return redirect(url_for("workspace.index"))

    lesson_plan = get_teacher_lesson_plan_or_404(lesson_plan_id)

    if not lesson_plan.generated_content:
        flash(
            "Generate the lesson plan before viewing the FCT-EMIS format.",
            "warning",
        )
        return redirect(
            url_for(
                "teacher.lesson_plan_preview",
                lesson_plan_id=lesson_plan.id,
            )
        )

    try:
        generated_content = json.loads(lesson_plan.generated_content)
    except (TypeError, json.JSONDecodeError):
        flash(
            "The saved AI lesson content could not be read.",
            "danger",
        )
        return redirect(
            url_for(
                "teacher.lesson_plan_preview",
                lesson_plan_id=lesson_plan.id,
            )
        )

    fct_emis = build_fct_emis_view_model(
        lesson_plan,
        generated_content,
    )

    return render_template(
        "teacher/fct_emis_lesson_plan.html",
        lesson_plan=lesson_plan,
        fct_emis=fct_emis,
    )