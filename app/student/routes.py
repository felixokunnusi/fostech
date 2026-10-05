from datetime import datetime

from flask import flash, redirect, render_template, url_for, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentQuestion,
)

from . import student_bp
from app.utils import now_utc
from app.models.school_membership import SchoolMembership
from app.models.category_subject_config import CategorySubjectConfig
from app.models.subject_selection_rule import SubjectSelectionRule
from app.models.student_subject_enrollment import StudentSubjectEnrollment
from app.student.subject_selection import validate_subject_selection
from app.models.class_group import ClassGroup
from app.models.subject_category import SubjectCategory


def student_has_access():
    return (
        current_user.is_authenticated
        and any(
            role.role == "student"
            for role in current_user.roles
        )
    )


@student_bp.route("/")
@login_required
def dashboard():
    if not student_has_access():
        flash(
            "You do not have access to the Student workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    now = now_utc()

    assessments = (
        Assessment.query
        .filter(
            Assessment.status == "published",
            db.or_(
                Assessment.start_at.is_(None),
                Assessment.start_at <= now,
            ),
            db.or_(
                Assessment.due_at.is_(None),
                Assessment.due_at >= now,
            ),
        )
        .order_by(Assessment.due_at.asc())
        .all()
    )

    return render_template(
        "student/dashboard.html",
        assessments=assessments,
    )

# ============================================================================
# STUDENT SUBJECT SELECTION
# ============================================================================

# ============================================================================
# STUDENT SUBJECT SELECTION
# ============================================================================

@student_bp.route(
    "/subjects",
    methods=["GET", "POST"],
)
@login_required
def subject_selection():
    """
    Display and process subject selection for the student's
    current school placement and class-group stream.
    """

    if not student_has_access():
        flash(
            "You do not have access to the Student workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    # ---------------------------------------------------------------
    # ACTIVE STUDENT PLACEMENT
    # ---------------------------------------------------------------

    membership = (
        SchoolMembership.query
        .filter_by(
            user_id=current_user.id,
            active=True,
            membership_type="student",
        )
        .order_by(
            SchoolMembership.created_at.desc()
        )
        .first()
    )

    if membership is None:
        flash(
            "You have not yet been placed in a school, class, and "
            "academic session. Please contact your school administrator.",
            "warning",
        )
        return redirect(url_for("student.dashboard"))

    # ---------------------------------------------------------------
    # GET THE STUDENT'S CLASS GROUP
    # ---------------------------------------------------------------

    class_group = None

    if membership.class_group_id:
        class_group = (
            ClassGroup.query
            .filter_by(
                id=membership.class_group_id,
                class_id=membership.class_id,
                active=True,
            )
            .first()
        )

    if class_group is None:
        flash(
            "Your class stream has not been configured. "
            "Please contact your school administrator.",
            "warning",
        )
        return redirect(url_for("student.dashboard"))

    # ---------------------------------------------------------------
    # STREAM CATEGORY
    # ---------------------------------------------------------------

    if not class_group.category_id:
        flash(
            "Your class stream does not have a subject category "
            "assigned to it.",
            "warning",
        )
        return redirect(url_for("student.dashboard"))

    stream_category = (
        SubjectCategory.query
        .filter_by(
            id=class_group.category_id,
            school_id=membership.school_id,
            active=True,
        )
        .first()
    )

    if stream_category is None:
        flash(
            "Your class stream category is invalid. "
            "Please contact your school administrator.",
            "danger",
        )
        return redirect(url_for("student.dashboard"))

    # ---------------------------------------------------------------
    # SCHOOL-WIDE SUBJECT SELECTION RULE
    # ---------------------------------------------------------------

    selection_rule = (
        SubjectSelectionRule.query
        .filter_by(
            school_id=membership.school_id,
            active=True,
        )
        .first()
    )

    if selection_rule is None:
        flash(
            "Your school has not yet configured the subject "
            "selection rules.",
            "warning",
        )
        return redirect(url_for("student.dashboard"))

    # ---------------------------------------------------------------
    # DETERMINE ALLOWED CATEGORIES
    #
    # ALL students:
    #     Core + Trade
    #
    # Science:
    #     Core + Trade + Science
    #
    # Business:
    #     Core + Trade + Business
    #
    # Humanities:
    #     Core + Trade + Humanities + Nigerian Language
    # ---------------------------------------------------------------

    all_categories = (
        SubjectCategory.query
        .filter_by(
            school_id=membership.school_id,
            active=True,
        )
        .order_by(
            SubjectCategory.name.asc()
        )
        .all()
    )

    category_by_name = {
        category.name.strip().casefold(): category
        for category in all_categories
    }

    allowed_categories = []

    core_category = category_by_name.get("core")
    trade_category = category_by_name.get("trade")

    if core_category:
        allowed_categories.append(core_category)

    if trade_category:
        allowed_categories.append(trade_category)

    # Student's stream.
    if stream_category.id not in {
        category.id
        for category in allowed_categories
    }:
        allowed_categories.append(stream_category)

    # Humanities students also get Nigerian Language.
    if (
        stream_category.name.strip().casefold()
        == "humanities"
    ):
        nigerian_language_category = category_by_name.get(
            "nigerian language"
        )

        if (
            nigerian_language_category
            and nigerian_language_category.id
            not in {
                category.id
                for category in allowed_categories
            }
        ):
            allowed_categories.append(
                nigerian_language_category
            )

    allowed_category_ids = {
        category.id
        for category in allowed_categories
    }

    # ---------------------------------------------------------------
    # LOAD SUBJECT CONFIGURATIONS
    # ---------------------------------------------------------------

    subject_configs = (
        CategorySubjectConfig.query
        .filter(
            CategorySubjectConfig.school_id
            == membership.school_id,
            CategorySubjectConfig.active.is_(True),
            CategorySubjectConfig.category_id.in_(
                allowed_category_ids
            ),
        )
        .filter(
            CategorySubjectConfig.subject.has(
                active=True
            )
        )
        .order_by(
            CategorySubjectConfig.category_id.asc(),
            CategorySubjectConfig.display_order.asc(),
            CategorySubjectConfig.id.asc(),
        )
        .all()
    )

    # ---------------------------------------------------------------
    # GROUP SUBJECTS BY CATEGORY
    # ---------------------------------------------------------------

    subjects_by_category = {
        category.id: []
        for category in allowed_categories
    }

    for config in subject_configs:
        subjects_by_category.setdefault(
            config.category_id,
            [],
        ).append(config)

    # ---------------------------------------------------------------
    # EXISTING ACTIVE ENROLLMENTS
    # ---------------------------------------------------------------

    existing_enrollments = (
        StudentSubjectEnrollment.query
        .filter_by(
            student_id=current_user.id,
            school_id=membership.school_id,
            academic_session_id=membership.academic_session_id,
            class_id=membership.class_id,
            class_group_id=membership.class_group_id,
            active=True,
        )
        .all()
    )

    existing_subject_ids = {
        enrollment.subject_id
        for enrollment in existing_enrollments
    }

    # Required subjects are always selected.
    required_subject_ids = {
        config.subject_id
        for config in subject_configs
        if config.required
    }

    # ===============================================================
    # PROCESS SUBMISSION
    # ===============================================================

    if request.method == "POST":

        submitted_subject_ids = request.form.getlist(
            "subject_ids"
        )

        try:
            selected_subject_ids = {
                int(subject_id)
                for subject_id in submitted_subject_ids
            }

        except (TypeError, ValueError):

            flash(
                "Invalid subject selection.",
                "danger",
            )

            return render_template(
                "student/subject_selection.html",
                membership=membership,
                class_group=class_group,
                stream_category=stream_category,
                selection_rule=selection_rule,
                allowed_categories=allowed_categories,
                subjects_by_category=subjects_by_category,
                selected_subject_ids=(
                    existing_subject_ids
                    | required_subject_ids
                ),
            )

        # Compulsory subjects cannot be removed.
        selected_subject_ids.update(
            required_subject_ids
        )

        # -----------------------------------------------------------
        # SERVER-SIDE VALIDATION
        # -----------------------------------------------------------

        validation = validate_subject_selection(
            membership.school_id,
            selected_subject_ids,
            stream_category.id,
        )

        if not validation["valid"]:

            for error in validation["errors"]:
                flash(
                    error,
                    "danger",
                )

            return render_template(
                "student/subject_selection.html",
                membership=membership,
                class_group=class_group,
                stream_category=stream_category,
                selection_rule=selection_rule,
                allowed_categories=allowed_categories,
                subjects_by_category=subjects_by_category,
                selected_subject_ids=selected_subject_ids,
            )

        # -----------------------------------------------------------
        # SAVE VALID SELECTION
        # -----------------------------------------------------------

        for enrollment in existing_enrollments:

            if enrollment.subject_id not in selected_subject_ids:
                enrollment.active = False

        existing_subject_ids = {
            enrollment.subject_id
            for enrollment in existing_enrollments
        }

        for subject_id in selected_subject_ids:

            if subject_id in existing_subject_ids:
                continue

            enrollment = StudentSubjectEnrollment(
                student_id=current_user.id,
                school_id=membership.school_id,
                academic_session_id=membership.academic_session_id,
                class_id=membership.class_id,
                class_group_id=membership.class_group_id,
                subject_id=subject_id,
                active=True,
            )

            db.session.add(enrollment)

        db.session.commit()

        flash(
            "Your subject selection has been submitted successfully.",
            "success",
        )

        return redirect(
            url_for("student.subject_selection")
        )

    # ===============================================================
    # DISPLAY
    # ===============================================================

    selected_subject_ids = (
        existing_subject_ids
        | required_subject_ids
    )

    return render_template(
        "student/subject_selection.html",
        membership=membership,
        class_group=class_group,
        stream_category=stream_category,
        selection_rule=selection_rule,
        allowed_categories=allowed_categories,
        subjects_by_category=subjects_by_category,
        selected_subject_ids=selected_subject_ids,
    )


@student_bp.route(
    "/assessments/<int:assessment_id>/start",
    methods=["GET"],
)
@login_required
def start_assessment(assessment_id):
    if not student_has_access():
        flash(
            "You do not have access to the Student workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    assessment = (
        Assessment.query
        .filter_by(
            id=assessment_id,
            status="published",
        )
        .first_or_404()
    )

    now = now_utc()

    if assessment.start_at and assessment.start_at > now:
        flash(
            "This assessment is not available yet.",
            "warning",
        )
        return redirect(url_for("student.dashboard"))

    if assessment.due_at and assessment.due_at < now:
        flash(
            "This assessment is no longer available.",
            "warning",
        )
        return redirect(url_for("student.dashboard"))

    # ---------------------------------------------------------
    # GRADED MODE
    # ---------------------------------------------------------
    # A graded assessment allows exactly one attempt.
    # If the student has already submitted one, access is denied.
    if assessment.mode == "graded":

        submitted_attempt = (
            AssessmentAttempt.query
            .filter_by(
                assessment_id=assessment.id,
                student_id=current_user.id,
                status="submitted",
            )
            .first()
        )

        if submitted_attempt:
            flash(
                "You have already completed this graded assessment. "
                "A second attempt is not allowed.",
                "warning",
            )
            return redirect(
                url_for(
                    "student.assessment_result",
                    attempt_id=submitted_attempt.id,
                )
            )

    # ---------------------------------------------------------
    # EXISTING IN-PROGRESS ATTEMPT
    # ---------------------------------------------------------
    # If the student has an unfinished attempt, resume it.
    attempt = (
        AssessmentAttempt.query
        .filter_by(
            assessment_id=assessment.id,
            student_id=current_user.id,
            status="in_progress",
        )
        .first()
    )

    if attempt:
        return redirect(
            url_for(
                "student.take_assessment",
                attempt_id=attempt.id,
            )
        )

    # ---------------------------------------------------------
    # CREATE NEW ATTEMPT
    # ---------------------------------------------------------
    attempt = AssessmentAttempt(
        assessment_id=assessment.id,
        student_id=current_user.id,
        status="in_progress",
        total_marks=assessment.total_marks,
    )

    db.session.add(attempt)
    db.session.commit()

    flash("Assessment started.", "success")

    return redirect(
        url_for(
            "student.take_assessment",
            attempt_id=attempt.id,
        )
    )


@student_bp.route(
    "/attempts/<int:attempt_id>",
    methods=["GET"],
)
@login_required
def take_assessment(attempt_id):
    if not student_has_access():
        flash(
            "You do not have access to the Student workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    attempt = (
        AssessmentAttempt.query
        .filter_by(
            id=attempt_id,
            student_id=current_user.id,
        )
        .first_or_404()
    )

    if attempt.status != "in_progress":
        flash(
            "This assessment attempt has already been submitted.",
            "warning",
        )
        return redirect(url_for("student.dashboard"))

    assessment = attempt.assessment

    if assessment.status != "published":
        flash(
            "This assessment is no longer available.",
            "warning",
        )
        return redirect(url_for("student.dashboard"))

    now = now_utc()

    if assessment.start_at and assessment.start_at > now:
        flash(
            "This assessment is not available yet.",
            "warning",
        )
        return redirect(url_for("student.dashboard"))

    if assessment.due_at and assessment.due_at < now:
        flash(
            "This assessment is no longer available.",
            "warning",
        )
        return redirect(url_for("student.dashboard"))

    questions = (
        AssessmentQuestion.query
        .filter_by(
            assessment_id=assessment.id,
        )
        .order_by(
            AssessmentQuestion.question_number.asc()
        )
        .all()
    )

    return render_template(
        "student/take_assessment.html",
        attempt=attempt,
        assessment=assessment,
        questions=questions,
    )

@student_bp.route(
    "/attempts/<int:attempt_id>/submit",
    methods=["POST"],
)
@login_required
def submit_assessment(attempt_id):
    if not student_has_access():
        flash(
            "You do not have access to the Student workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    attempt = (
        AssessmentAttempt.query
        .filter_by(
            id=attempt_id,
            student_id=current_user.id,
        )
        .first_or_404()
    )

    if attempt.status != "in_progress":
        flash(
            "This assessment attempt has already been submitted.",
            "warning",
        )
        return redirect(url_for("student.dashboard"))

    assessment = attempt.assessment

    if assessment.status != "published":
        flash(
            "This assessment is no longer available.",
            "warning",
        )
        return redirect(url_for("student.dashboard"))

    questions = (
        AssessmentQuestion.query
        .filter_by(
            assessment_id=assessment.id,
        )
        .order_by(
            AssessmentQuestion.question_number.asc()
        )
        .all()
    )

    total_score = 0

    for question in questions:

        field_name = f"question_{question.id}"
        submitted_answer = request.form.get(field_name)

        if submitted_answer is not None:
            submitted_answer = submitted_answer.strip()

        marks_awarded = 0
        is_correct = None

        # --------------------------------------------------
        # MCQ AUTO-GRADING
        # --------------------------------------------------
        if question.question_type == "mcq":

            is_correct = False

            if submitted_answer:

                correct_answer = (
                    question.correct_answer or ""
                ).strip()

                # Compare answer letters first.
                if submitted_answer.upper() == correct_answer.upper():
                    is_correct = True

                else:
                    # Also support correct answers stored as
                    # the actual option text.
                    option_map = {
                        "A": question.option_a,
                        "B": question.option_b,
                        "C": question.option_c,
                        "D": question.option_d,
                    }

                    selected_text = option_map.get(
                        submitted_answer.upper()
                    )

                    if (
                        selected_text
                        and correct_answer
                        and selected_text.strip().casefold()
                        == correct_answer.casefold()
                    ):
                        is_correct = True

            if is_correct:
                marks_awarded = question.marks
                total_score += question.marks

        # --------------------------------------------------
        # SHORT ANSWER
        # --------------------------------------------------
        elif question.question_type == "short_answer":
            # Short-answer grading will remain pending
            # for teacher review for now.
            is_correct = None
            marks_awarded = 0

        # --------------------------------------------------
        # THEORY / ESSAY
        # --------------------------------------------------
        elif question.question_type == "theory":
            # Theory questions require teacher grading.
            is_correct = None
            marks_awarded = 0

        answer = AssessmentAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            answer_text=submitted_answer,
            marks_awarded=marks_awarded,
            is_correct=is_correct,
        )

        db.session.add(answer)

    attempt.submitted_at = now_utc()
    attempt.status = "submitted"
    attempt.score = total_score
    attempt.total_marks = assessment.total_marks

    db.session.commit()

    flash(
        "Assessment submitted successfully.",
        "success",
    )

    return redirect(
        url_for(
            "student.assessment_result",
            attempt_id=attempt.id,
        )
    )

@student_bp.route(
    "/attempts/<int:attempt_id>/result",
)
@login_required
def assessment_result(attempt_id):
    if not student_has_access():
        flash(
            "You do not have access to the Student workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    attempt = (
        AssessmentAttempt.query
        .filter_by(
            id=attempt_id,
            student_id=current_user.id,
        )
        .first_or_404()
    )

    if attempt.status != "submitted":
        flash(
            "This assessment has not been submitted yet.",
            "warning",
        )
        return redirect(
            url_for(
                "student.take_assessment",
                attempt_id=attempt.id,
            )
        )

    return render_template(
        "student/assessment_result.html",
        attempt=attempt,
        assessment=attempt.assessment,
    )