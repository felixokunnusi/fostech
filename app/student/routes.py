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