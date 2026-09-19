"""
Teacher Lesson Plan PDF Service

Generates PDF documents from the existing FCT-EMIS lesson-plan HTML
template using WeasyPrint.

This module handles PDF rendering only.
It does not generate lesson content and does not modify the database.
"""

from pathlib import Path

from flask import render_template
from weasyprint import HTML


def generate_lesson_plan_pdf(lesson_plan, fct_emis):
    """
    Generate an FCT-EMIS lesson-plan PDF.

    Args:
        lesson_plan: LessonPlan database object.
        fct_emis: Prepared FCT-EMIS view model.

    Returns:
        bytes: Generated PDF data.
    """

    html_content = render_template(
        "teacher/fct_emis_lesson_plan_pdf.html",
        lesson_plan=lesson_plan,
        fct_emis=fct_emis,
    )

    base_url = Path.cwd().as_uri()

    pdf = HTML(
        string=html_content,
        base_url=base_url,
    ).write_pdf()

    return pdf