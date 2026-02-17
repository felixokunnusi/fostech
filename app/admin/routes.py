# app/admin/routes.py

from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required
from werkzeug.utils import secure_filename

from app.utils import admin_required
from . import admin_bp
from .importer import import_questions_from_csv_file

ALLOWED_EXTENSIONS = {"csv"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_bp.route("/upload-questions", methods=["GET", "POST"])
@login_required
@admin_required
def upload_questions():
    if request.method == "GET":
        return render_template("admin/upload_questions.html")

    file = request.files.get("file")
    if not file or not file.filename:
        flash("Please select a CSV file.", "warning")
        return redirect(url_for("admin.upload_questions"))

    if not allowed_file(file.filename):
        flash("Only .csv files are allowed.", "danger")
        return redirect(url_for("admin.upload_questions"))

    filename = secure_filename(file.filename)

    try:
        summary = import_questions_from_csv_file(file)
    except Exception as e:
        flash(f"Import failed: {e}", "danger")
        return redirect(url_for("admin.upload_questions"))

    if summary and summary.get("errors"):
        flash(f"Imported with errors from {filename}. See details below.", "warning")
    else:
        flash(f"✅ Import successful: {filename}", "success")

    return render_template("admin/upload_questions.html", summary=summary, filename=filename)
