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
from app.models.assessment_attempt import AssessmentAttempt

from app.extensions import db
from app.models import (
    Assessment,
    AssessmentQuestion,
    LessonPlan,
)
from app.teacher.ai.lesson_plan import (
    LessonPlanAIError,
    generate_lesson_plan,
)
from app.teacher.ai.assessment import (
    AssessmentAIError,
    generate_assessment_questions,
)
from app.models.assessment_answer import AssessmentAnswer
from app.teacher.renderers.fct_emis import build_fct_emis_view_model

from . import teacher_bp
from .pdf import generate_lesson_plan_pdf
from .forms import (
    AssessmentAIGenerationForm,
    AssessmentForm,
    AssessmentQuestionForm,
    GeneratedLessonPlanForm,
    LessonPlanForm,
)

from app.utils import nigeria_to_utc, utc_to_nigeria

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


def validate_assessment_for_publication(assessment):
    """
    Validate an assessment before it can be published.

    Returns:
        list[str]: Validation errors.
    """

    errors = []

    # Basic assessment information
    if not assessment.title or not assessment.title.strip():
        errors.append("Assessment title is required.")

    if not assessment.subject or not assessment.subject.strip():
        errors.append("Subject is required.")

    if not assessment.class_name or not assessment.class_name.strip():
        errors.append("Class is required.")

    if not assessment.topic or not assessment.topic.strip():
        errors.append("Topic is required.")

    # Questions
    questions = (
        AssessmentQuestion.query
        .filter_by(assessment_id=assessment.id)
        .order_by(AssessmentQuestion.question_number.asc())
        .all()
    )

    if not questions:
        errors.append(
            "The assessment must contain at least one question."
        )
        return errors

    # Validate each question
    for number, question in enumerate(questions, start=1):

        question_label = f"Question {number}"

        if not question.question_text or not question.question_text.strip():
            errors.append(
                f"{question_label}: question text is required."
            )

        if not question.marks or question.marks < 1:
            errors.append(
                f"{question_label}: marks must be at least 1."
            )

        if question.question_type == "mcq":

            if not question.option_a or not question.option_a.strip():
                errors.append(
                    f"{question_label}: Option A is required."
                )

            if not question.option_b or not question.option_b.strip():
                errors.append(
                    f"{question_label}: Option B is required."
                )

            if not question.option_c or not question.option_c.strip():
                errors.append(
                    f"{question_label}: Option C is required."
                )

            if not question.option_d or not question.option_d.strip():
                errors.append(
                    f"{question_label}: Option D is required."
                )

            if (
                not question.correct_answer
                or not question.correct_answer.strip()
            ):
                errors.append(
                    f"{question_label}: correct answer is required."
                )

    # Date validation
    if assessment.start_at and assessment.due_at:
        if assessment.due_at <= assessment.start_at:
            errors.append(
                "The due date/time must be later than the start date/time."
            )

    return errors

@teacher_bp.route(
    "/assessments/<int:assessment_id>/validate",
    methods=["POST"],
)
@login_required
def validate_assessment(assessment_id):
    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    assessment = (
        Assessment.query
        .filter_by(
            id=assessment_id,
            teacher_id=current_user.id,
        )
        .first_or_404()
    )

    if assessment.status != "draft":
        flash(
            "Only draft assessments can be validated for publication.",
            "warning",
        )
        return redirect(
            url_for(
                "teacher.manage_assessment",
                assessment_id=assessment.id,
            )
        )

    errors = validate_assessment_for_publication(assessment)

    if errors:
        for error in errors:
            flash(error, "danger")

        return redirect(
            url_for(
                "teacher.manage_assessment",
                assessment_id=assessment.id,
            )
        )

    flash(
        "Assessment passed all publication checks. "
        "It is ready to be published.",
        "success",
    )

    return redirect(
        url_for(
            "teacher.manage_assessment",
            assessment_id=assessment.id,
        )
    )


@teacher_bp.route(
    "/assessments/<int:assessment_id>/publish",
    methods=["POST"],
)
@login_required
def publish_assessment(assessment_id):
    """
    Publish a draft assessment after it passes all publication checks.
    """

    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    assessment = (
        Assessment.query
        .filter_by(
            id=assessment_id,
            teacher_id=current_user.id,
        )
        .first_or_404()
    )

    if assessment.status != "draft":
        flash(
            "Only draft assessments can be published.",
            "warning",
        )
        return redirect(
            url_for(
                "teacher.manage_assessment",
                assessment_id=assessment.id,
            )
        )

    errors = validate_assessment_for_publication(assessment)

    if errors:
        for error in errors:
            flash(error, "danger")

        return redirect(
            url_for(
                "teacher.manage_assessment",
                assessment_id=assessment.id,
            )
        )

    assessment.status = "published"

    db.session.commit()

    flash(
        "Assessment published successfully. It is now available to students.",
        "success",
    )

    return redirect(
        url_for(
            "teacher.manage_assessment",
            assessment_id=assessment.id,
        )
    )

@teacher_bp.route(
    "/assessments/<int:assessment_id>/close",
    methods=["POST"],
)
@login_required
def close_assessment(assessment_id):
    """
    Close a published assessment so that students can no longer start
    new attempts.
    """

    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    assessment = (
        Assessment.query
        .filter_by(
            id=assessment_id,
            teacher_id=current_user.id,
        )
        .first_or_404()
    )

    if assessment.status != "published":
        flash(
            "Only published assessments can be closed.",
            "warning",
        )
        return redirect(
            url_for(
                "teacher.manage_assessment",
                assessment_id=assessment.id,
            )
        )

    assessment.status = "closed"
    db.session.commit()

    flash(
        "Assessment closed successfully. Students can no longer start new attempts.",
        "success",
    )

    return redirect(
        url_for(
            "teacher.manage_assessment",
            assessment_id=assessment.id,
        )
    )


@teacher_bp.route("/assessments")
@login_required
def assessments():
    """
    Display assessments belonging to the current teacher.
    """

    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    assessments = (
        Assessment.query
        .filter_by(teacher_id=current_user.id)
        .order_by(Assessment.updated_at.desc())
        .all()
    )

    return render_template(
        "teacher/assessments.html",
        assessments=assessments,
        utc_to_nigeria=utc_to_nigeria,
    )

@teacher_bp.route(
    "/assessments/new",
    methods=["GET", "POST"],
)
@login_required
def new_assessment():
    """
    Create a new assessment draft.
    """

    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    form = AssessmentForm()

    if form.validate_on_submit():

        assessment = Assessment(
            teacher_id=current_user.id,
            title=form.title.data,
            subject=form.subject.data,
            class_name=form.class_name.data,
            topic=form.topic.data,
            assessment_type=form.assessment_type.data,
            mode=form.mode.data,
            instructions=form.instructions.data,
            start_at=nigeria_to_utc(form.start_at.data),
            due_at=nigeria_to_utc(form.due_at.data),
            status="draft",
            total_marks=0,
        )

        db.session.add(assessment)
        db.session.commit()

        flash(
            "Assessment draft created successfully.",
            "success",
        )

        return redirect(
            url_for(
                "teacher.assessments",
            )
        )

    return render_template(
        "teacher/assessment_form.html",
        form=form,
        edit_mode=False,
    )

@teacher_bp.route(
    "/assessments/<int:assessment_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_assessment(assessment_id):
    """
    Edit the basic details of a draft assessment.
    """

    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    assessment = (
        Assessment.query
        .filter_by(
            id=assessment_id,
            teacher_id=current_user.id,
        )
        .first_or_404()
    )

    if assessment.status != "draft":
        flash(
            "Only draft assessments can be edited.",
            "warning",
        )
        return redirect(
            url_for(
                "teacher.manage_assessment",
                assessment_id=assessment.id,
            )
        )

    form = AssessmentForm(obj=assessment)

    if request.method == "GET":
        form.start_at.data = utc_to_nigeria(assessment.start_at)
        form.due_at.data = utc_to_nigeria(assessment.due_at)

    if form.validate_on_submit():
        assessment.title = form.title.data
        assessment.subject = form.subject.data
        assessment.class_name = form.class_name.data
        assessment.topic = form.topic.data
        assessment.assessment_type = form.assessment_type.data
        assessment.mode = form.mode.data
        assessment.instructions = form.instructions.data

        assessment.start_at = nigeria_to_utc(
            form.start_at.data
        )
        assessment.due_at = nigeria_to_utc(
            form.due_at.data
        )

        db.session.commit()

        flash(
            "Assessment details updated successfully.",
            "success",
        )

        return redirect(
            url_for(
                "teacher.manage_assessment",
                assessment_id=assessment.id,
            )
        )

    return render_template(
        "teacher/assessment_form.html",
        form=form,
        edit_mode=True,
        assessment=assessment,
    )

@teacher_bp.route(
    "/assessments/<int:assessment_id>",
)
@login_required
def manage_assessment(assessment_id):
    """
    Display an assessment and its questions.
    """

    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    assessment = (
        Assessment.query
        .filter_by(
            id=assessment_id,
            teacher_id=current_user.id,
        )
        .first_or_404()
    )

    return render_template(
        "teacher/manage_assessment.html",
        assessment=assessment,
    )

@teacher_bp.route(
    "/assessments/<int:assessment_id>/attempts",
    methods=["GET"],
)
@login_required
def assessment_attempts(assessment_id):
    """
    View student attempts for an assessment.
    """

    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    assessment = (
        Assessment.query
        .filter_by(
            id=assessment_id,
            teacher_id=current_user.id,
        )
        .first_or_404()
    )

    attempts = (
        AssessmentAttempt.query
        .filter_by(assessment_id=assessment.id)
        .order_by(AssessmentAttempt.started_at.desc())
        .all()
    )

    return render_template(
        "teacher/assessment_attempts.html",
        assessment=assessment,
        attempts=attempts,
        utc_to_nigeria=utc_to_nigeria,
    )

@teacher_bp.route(
    "/assessments/<int:assessment_id>/questions/new",
    methods=["GET", "POST"],
)
@login_required
def new_assessment_question(assessment_id):
    """
    Add a question to an existing assessment.
    """

    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    assessment = (
        Assessment.query
        .filter_by(
            id=assessment_id,
            teacher_id=current_user.id,
        )
        .first_or_404()
    )

    if assessment.status != "draft":
        flash(
            "Questions can only be added while the assessment is a draft.",
            "warning",
        )
        return redirect(
            url_for(
                "teacher.manage_assessment",
                assessment_id=assessment.id,
            )
        )

    form = AssessmentQuestionForm()

    if form.validate_on_submit():

        next_question_number = (
            AssessmentQuestion.query
            .filter_by(assessment_id=assessment.id)
            .count()
            + 1
        )

        question = AssessmentQuestion(
            assessment_id=assessment.id,
            question_number=next_question_number,
            question_type=form.question_type.data,
            question_text=form.question_text.data,
            option_a=form.option_a.data,
            option_b=form.option_b.data,
            option_c=form.option_c.data,
            option_d=form.option_d.data,
            correct_answer=form.correct_answer.data,
            marks=form.marks.data,
            explanation=form.explanation.data,
        )

        db.session.add(question)

        assessment.total_marks += form.marks.data

        db.session.commit()

        flash(
            "Question added successfully.",
            "success",
        )

        return redirect(
            url_for(
                "teacher.manage_assessment",
                assessment_id=assessment.id,
            )
        )

    return render_template(
        "teacher/assessment_question_form.html",
        form=form,
        assessment=assessment,
        edit_mode=False,
    )

@teacher_bp.route(
    "/assessments/<int:assessment_id>/questions/generate",
    methods=["GET", "POST"],
)
@login_required
def generate_assessment_questions_ai(assessment_id):
    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    assessment = (
        Assessment.query
        .filter_by(
            id=assessment_id,
            teacher_id=current_user.id,
        )
        .first_or_404()
    )

    if assessment.status != "draft":
        flash(
            "AI questions can only be generated while the assessment is a draft.",
            "warning",
        )
        return redirect(
            url_for(
                "teacher.manage_assessment",
                assessment_id=assessment.id,
            )
        )

    if not assessment.topic:
        flash(
            "Please set an assessment topic before generating questions with AI.",
            "warning",
        )
        return redirect(
            url_for(
                "teacher.manage_assessment",
                assessment_id=assessment.id,
            )
        )

    form = AssessmentAIGenerationForm()

    if form.validate_on_submit():
        try:
            generated_questions = generate_assessment_questions(
                subject=assessment.subject,
                class_name=assessment.class_name,
                topic=assessment.topic,
                number_of_questions=form.number_of_questions.data,
                question_type=form.question_type.data,
                difficulty=form.difficulty.data,
                examination_relevance=form.examination_relevance.data,
                additional_instructions=form.additional_instructions.data,
            )

            existing_count = (
                AssessmentQuestion.query
                .filter_by(assessment_id=assessment.id)
                .count()
            )

            next_question_number = existing_count + 1
            added_marks = 0

            for index, generated in enumerate(
                generated_questions,
                start=next_question_number,
            ):
                question = AssessmentQuestion(
                    assessment_id=assessment.id,
                    question_number=index,
                    question_type=generated["question_type"],
                    question_text=generated["question_text"],
                    option_a=generated.get("option_a"),
                    option_b=generated.get("option_b"),
                    option_c=generated.get("option_c"),
                    option_d=generated.get("option_d"),
                    correct_answer=generated.get("correct_answer"),
                    marks=generated["marks"],
                    explanation=generated.get("explanation"),
                )

                db.session.add(question)
                added_marks += generated["marks"]

            assessment.total_marks += added_marks

            db.session.commit()

            flash(
                f"{len(generated_questions)} AI-generated question(s) "
                "were added as draft questions. Review and edit them "
                "before publishing the assessment.",
                "success",
            )

            return redirect(
                url_for(
                    "teacher.manage_assessment",
                    assessment_id=assessment.id,
                )
            )

        except AssessmentAIError as exc:
            db.session.rollback()

            flash(
                f"AI question generation failed: {exc}",
                "danger",
            )

        except Exception:
            db.session.rollback()

            flash(
                "An unexpected error occurred while generating "
                "assessment questions.",
                "danger",
            )

    return render_template(
        "teacher/assessment_ai_generation_form.html",
        form=form,
        assessment=assessment,
    )

@teacher_bp.route(
    "/assessments/<int:assessment_id>/questions/<int:question_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_assessment_question(assessment_id, question_id):
    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    assessment = (
        Assessment.query
        .filter_by(
            id=assessment_id,
            teacher_id=current_user.id,
        )
        .first_or_404()
    )

    question = (
        AssessmentQuestion.query
        .filter_by(
            id=question_id,
            assessment_id=assessment.id,
        )
        .first_or_404()
    )

    if assessment.status != "draft":
        flash(
            "Questions can only be edited while the assessment is a draft.",
            "warning",
        )
        return redirect(
            url_for(
                "teacher.manage_assessment",
                assessment_id=assessment.id,
            )
        )

    form = AssessmentQuestionForm(obj=question)

    if form.validate_on_submit():
        old_marks = question.marks

        question.question_type = form.question_type.data
        question.question_text = form.question_text.data
        question.option_a = form.option_a.data
        question.option_b = form.option_b.data
        question.option_c = form.option_c.data
        question.option_d = form.option_d.data
        question.correct_answer = form.correct_answer.data
        question.marks = form.marks.data
        question.explanation = form.explanation.data

        assessment.total_marks += (
            form.marks.data - old_marks
        )

        db.session.commit()

        flash(
            "Question updated successfully.",
            "success",
        )

        return redirect(
            url_for(
                "teacher.manage_assessment",
                assessment_id=assessment.id,
            )
        )

    return render_template(
        "teacher/assessment_question_form.html",
        form=form,
        assessment=assessment,
        question=question,
        edit_mode=True,
    )

@teacher_bp.route(
    "/assessments/<int:assessment_id>/questions/<int:question_id>/delete",
    methods=["POST"],
)
@login_required
def delete_assessment_question(assessment_id, question_id):
    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    assessment = (
        Assessment.query
        .filter_by(
            id=assessment_id,
            teacher_id=current_user.id,
        )
        .first_or_404()
    )

    question = (
        AssessmentQuestion.query
        .filter_by(
            id=question_id,
            assessment_id=assessment.id,
        )
        .first_or_404()
    )

    if assessment.status != "draft":
        flash(
            "Questions can only be deleted while the assessment is a draft.",
            "warning",
        )
        return redirect(
            url_for(
                "teacher.manage_assessment",
                assessment_id=assessment.id,
            )
        )

    db.session.delete(question)
    db.session.flush()

    remaining_questions = (
        AssessmentQuestion.query
        .filter_by(assessment_id=assessment.id)
        .order_by(AssessmentQuestion.question_number.asc())
        .all()
    )

    for number, remaining_question in enumerate(
        remaining_questions,
        start=1,
    ):
        remaining_question.question_number = number

    assessment.total_marks = sum(
        question.marks
        for question in remaining_questions
    )

    db.session.commit()

    flash(
        "Question deleted successfully and the assessment was renumbered.",
        "success",
    )

    return redirect(
        url_for(
            "teacher.manage_assessment",
            assessment_id=assessment.id,
        )
    )

@teacher_bp.route(
    "/assessments/<int:assessment_id>/attempts/<int:attempt_id>",
    methods=["GET"],
)
@login_required
def view_assessment_attempt(assessment_id, attempt_id):
    """
    View one student's assessment attempt.
    """

    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    assessment = (
        Assessment.query
        .filter_by(
            id=assessment_id,
            teacher_id=current_user.id,
        )
        .first_or_404()
    )

    attempt = (
        AssessmentAttempt.query
        .filter_by(
            id=attempt_id,
            assessment_id=assessment.id,
        )
        .first_or_404()
    )

    answers = (
        AssessmentAnswer.query
        .filter_by(attempt_id=attempt.id)
        .order_by(AssessmentAnswer.question_id.asc())
        .all()
    )

    return render_template(
        "teacher/view_assessment_attempt.html",
        assessment=assessment,
        attempt=attempt,
        answers=answers,
        utc_to_nigeria=utc_to_nigeria,
    )

@teacher_bp.route(
    "/assessments/<int:assessment_id>/attempts/<int:attempt_id>/answers/<int:answer_id>/grade",
    methods=["POST"],
)
@login_required
def grade_assessment_answer(
    assessment_id,
    attempt_id,
    answer_id,
):
    """
    Grade one student answer and recalculate the attempt score.
    """

    if not teacher_has_access():
        flash(
            "You do not have access to the Teacher workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    assessment = (
        Assessment.query
        .filter_by(
            id=assessment_id,
            teacher_id=current_user.id,
        )
        .first_or_404()
    )

    attempt = (
        AssessmentAttempt.query
        .filter_by(
            id=attempt_id,
            assessment_id=assessment.id,
        )
        .first_or_404()
    )

    answer = (
        AssessmentAnswer.query
        .filter_by(
            id=answer_id,
            attempt_id=attempt.id,
        )
        .first_or_404()
    )

    marks_raw = request.form.get("marks_awarded", "").strip()
    teacher_feedback = request.form.get(
        "teacher_feedback",
        "",
    ).strip()

    try:
        marks_awarded = int(marks_raw)
    except (TypeError, ValueError):
        flash(
            "Marks awarded must be a whole number.",
            "danger",
        )
        return redirect(
            url_for(
                "teacher.view_assessment_attempt",
                assessment_id=assessment.id,
                attempt_id=attempt.id,
            )
        )

    if marks_awarded < 0:
        flash(
            "Marks awarded cannot be negative.",
            "danger",
        )
        return redirect(
            url_for(
                "teacher.view_assessment_attempt",
                assessment_id=assessment.id,
                attempt_id=attempt.id,
            )
        )

    if marks_awarded > answer.question.marks:
        flash(
            f"Marks awarded cannot exceed the question's "
            f"maximum of {answer.question.marks}.",
            "danger",
        )
        return redirect(
            url_for(
                "teacher.view_assessment_attempt",
                assessment_id=assessment.id,
                attempt_id=attempt.id,
            )
        )

    answer.marks_awarded = marks_awarded
    answer.teacher_feedback = teacher_feedback

    if marks_awarded == answer.question.marks:
        answer.is_correct = True
    elif marks_awarded == 0:
        answer.is_correct = False
    else:
        answer.is_correct = None

    total_score = sum(
        (item.marks_awarded or 0)
        for item in attempt.answers
    )

    attempt.score = total_score

    db.session.commit()

    flash(
        "Answer graded successfully.",
        "success",
    )

    return redirect(
        url_for(
            "teacher.view_assessment_attempt",
            assessment_id=assessment.id,
            attempt_id=attempt.id,
        )
    )