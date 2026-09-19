"""
Teacher Workspace Routes

Handles:
- Teacher workspace dashboard
- Lesson plan creation
- Lesson plan preview
- AI lesson-plan generation
- FCT-EMIS lesson-plan rendering
- Lesson-plan PDF generation

AI-generated lesson content is stored as structured JSON text in the
LessonPlan.generated_content field.

Presentation/rendering remains separate from AI generation.
"""

import json
from io import BytesIO

from flask import (
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from app.extensions import db
from app.models import LessonPlan
from app.teacher.ai.lesson_plan import (
    LessonPlanAIError,
    generate_lesson_plan,
)
from app.teacher.renderers.fct_emis import build_fct_emis_view_model

from . import teacher_bp
from .pdf import generate_lesson_plan_pdf
from .forms import GeneratedLessonPlanForm, LessonPlanForm


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

    lesson_plans = (
        LessonPlan.query
        .filter_by(user_id=current_user.id)
        .order_by(LessonPlan.updated_at.desc())
        .all()
    )

    return render_template(
        "teacher/dashboard.html",
        lesson_plans=lesson_plans,
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
    "/lesson-plans/<int:lesson_plan_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_lesson_plan(lesson_plan_id):
    """
    Edit an existing lesson-plan draft.

    Editing updates the lesson-plan input data but does not
    automatically regenerate the AI-generated content.
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

    form = LessonPlanForm(obj=lesson_plan)

    if form.validate_on_submit():
        lesson_plan.format_key = form.format_key.data
        lesson_plan.lesson_date = form.lesson_date.data
        lesson_plan.class_name = form.class_name.data
        lesson_plan.number_in_class = form.number_in_class.data
        lesson_plan.average_age = form.average_age.data
        lesson_plan.subject = form.subject.data
        lesson_plan.lesson_topic = form.lesson_topic.data
        lesson_plan.unit_topic = form.unit_topic.data
        lesson_plan.start_time = form.start_time.data
        lesson_plan.end_time = form.end_time.data
        lesson_plan.duration_minutes = form.duration_minutes.data
        lesson_plan.learning_materials = form.learning_materials.data
        lesson_plan.curriculum = form.curriculum.data
        lesson_plan.examination_relevance = (
            form.examination_relevance.data or None
        )

        lesson_plan.status = (
            "needs_regeneration"
            if lesson_plan.generated_content
            else "draft"
        )

        db.session.commit()

        if lesson_plan.status == "needs_regeneration":
            flash(
                "Lesson plan updated. The existing AI content may no longer "
                "match the revised lesson details. Please regenerate the "
                "lesson plan.",
                "warning",
            )
        else:
            flash(
                "Lesson plan updated successfully.",
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
        edit_mode=True,
        lesson_plan=lesson_plan,
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
    "/lesson-plans/<int:lesson_plan_id>/edit-content",
    methods=["GET", "POST"],
)
@login_required
def edit_generated_lesson_plan(lesson_plan_id):
    """
    Edit the AI-generated lesson-plan content manually.

    This route allows the teacher to modify the generated content
    without changing the original lesson-plan details and without
    triggering AI regeneration.
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

    if not lesson_plan.generated_content:
        flash(
            "There is no generated lesson content to edit.",
            "warning",
        )
        return redirect(
            url_for(
                "teacher.lesson_plan_preview",
                lesson_plan_id=lesson_plan.id,
            )
        )

    try:
        generated_content = json.loads(
            lesson_plan.generated_content
        )
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

    form = GeneratedLessonPlanForm()

    if request.method == "GET":
        objectives = generated_content.get(
            "lesson_objectives",
            [],
        )

        if isinstance(objectives, list):
            form.lesson_objectives.data = "\n".join(
                str(objective)
                for objective in objectives
            )
        else:
            form.lesson_objectives.data = str(objectives or "")

        for stage_key in (
            "prior_ideas",
            "exploration",
            "discussion",
            "application",
            "evaluation",
        ):
            stage = generated_content.get(
                stage_key,
                {},
            )

            if not isinstance(stage, dict):
                stage = {}

            getattr(
                form,
                f"{stage_key}_mode",
            ).data = stage.get("mode", "")

            getattr(
                form,
                f"{stage_key}_teacher_activities",
            ).data = stage.get(
                "teacher_activities",
                "",
            )

            getattr(
                form,
                f"{stage_key}_student_activities",
            ).data = stage.get(
                "student_activities",
                "",
            )

        references = generated_content.get(
            "references",
            [],
        )

        if isinstance(references, list):
            form.references.data = "\n".join(
                str(reference)
                for reference in references
            )
        else:
            form.references.data = str(references or "")

        form.home_task.data = generated_content.get(
            "home_task",
            "",
        )

    if form.validate_on_submit():

        objectives = [
            line.strip()
            for line in form.lesson_objectives.data.splitlines()
            if line.strip()
        ]

        references = [
            line.strip()
            for line in form.references.data.splitlines()
            if line.strip()
        ]

        updated_content = {
            "lesson_objectives": objectives,

            "prior_ideas": {
                "mode": form.prior_ideas_mode.data or "",
                "teacher_activities": (
                    form.prior_ideas_teacher_activities.data
                    or ""
                ),
                "student_activities": (
                    form.prior_ideas_student_activities.data
                    or ""
                ),
            },

            "exploration": {
                "mode": form.exploration_mode.data or "",
                "teacher_activities": (
                    form.exploration_teacher_activities.data
                    or ""
                ),
                "student_activities": (
                    form.exploration_student_activities.data
                    or ""
                ),
            },

            "discussion": {
                "mode": form.discussion_mode.data or "",
                "teacher_activities": (
                    form.discussion_teacher_activities.data
                    or ""
                ),
                "student_activities": (
                    form.discussion_student_activities.data
                    or ""
                ),
            },

            "application": {
                "mode": form.application_mode.data or "",
                "teacher_activities": (
                    form.application_teacher_activities.data
                    or ""
                ),
                "student_activities": (
                    form.application_student_activities.data
                    or ""
                ),
            },

            "evaluation": {
                "mode": form.evaluation_mode.data or "",
                "teacher_activities": (
                    form.evaluation_teacher_activities.data
                    or ""
                ),
                "student_activities": (
                    form.evaluation_student_activities.data
                    or ""
                ),
            },

            "references": references,

            "home_task": (
                form.home_task.data
                or ""
            ),
        }

        lesson_plan.generated_content = json.dumps(
            updated_content,
            ensure_ascii=False,
        )

        lesson_plan.status = "generated"

        db.session.commit()

        flash(
            "Generated lesson plan updated successfully.",
            "success",
        )

        return redirect(
            url_for(
                "teacher.lesson_plan_preview",
                lesson_plan_id=lesson_plan.id,
            )
        )

    return render_template(
        "teacher/edit_generated_lesson_plan.html",
        form=form,
        lesson_plan=lesson_plan,
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

@teacher_bp.route("/lesson-plans/<int:lesson_plan_id>/pdf")
@login_required
def lesson_plan_pdf(lesson_plan_id):
    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    lesson_plan = get_teacher_lesson_plan_or_404(lesson_plan_id)

    if not lesson_plan.generated_content:
        flash(
            "Generate the lesson plan before downloading the PDF.",
            "warning",
        )
        return redirect(
            url_for(
                "teacher.lesson_plan_preview",
                lesson_plan_id=lesson_plan.id,
            )
        )

    try:
        generated_content = json.loads(
            lesson_plan.generated_content
        )
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

    try:
        pdf_data = generate_lesson_plan_pdf(
            lesson_plan,
            fct_emis,
        )
    except Exception:
        flash(
            "The lesson plan PDF could not be generated.",
            "danger",
        )
        return redirect(
            url_for(
                "teacher.lesson_plan_fct_emis",
                lesson_plan_id=lesson_plan.id,
            )
        )

    filename = (
        f"lesson_plan_{lesson_plan.id}_"
        f"{lesson_plan.lesson_topic}.pdf"
    )

    # Keep the filename safe for Windows and browsers.
    filename = "".join(
        character
        for character in filename
        if character.isalnum()
        or character in " ._-"
    )

    return send_file(
        BytesIO(pdf_data),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )

@teacher_bp.route(
    "/lesson-plans/<int:lesson_plan_id>/delete",
    methods=["POST"],
)
@login_required
def delete_lesson_plan(lesson_plan_id):
    """
    Delete an existing lesson plan belonging to the
    currently logged-in teacher.
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

    db.session.delete(lesson_plan)
    db.session.commit()

    flash(
        "Lesson plan deleted successfully.",
        "success",
    )

    return redirect(
        url_for("teacher.dashboard")
    )