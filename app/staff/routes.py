from datetime import datetime

from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models.school import School
from app.models.academic_session import AcademicSession
from app.models.school_class import SchoolClass
from app.models.class_group import ClassGroup
from app.models.subject import SchoolSubject
from app.models.user import User, UserRole
from app.models.school_membership import SchoolMembership
from app.models.subject_category import SubjectCategory
from app.models.category_rule import CategoryRule
from app.models.category_subject_config import CategorySubjectConfig
from app.models.subject_selection_rule import SubjectSelectionRule
from app.models.student_subject_selection import (
    StudentSubjectSelection,
    StudentSubjectSelectionItem,
)
from app.models.student_subject_enrollment import StudentSubjectEnrollment
from . import staff_bp


# ============================================================================
# ACCESS CONTROL
# ============================================================================

def staff_has_access():
    return (
        current_user.is_authenticated
        and current_user.is_staff
    )

def require_staff():
    """
    Centralized Staff workspace access check.

    Returns a redirect response when access is denied,
    otherwise returns None.
    """
    if not staff_has_access():
        flash(
            "You do not have access to the FOSTech Staff workspace.",
            "danger",
        )
        return redirect(url_for("workspace.index"))

    return None


# ============================================================================
# STAFF DASHBOARD
# ============================================================================

@staff_bp.route("/")
@login_required
def dashboard():
    access_response = require_staff()

    if access_response:
        return access_response

    return render_template("staff/dashboard.html")


# ============================================================================
# SCHOOL MANAGEMENT
# ============================================================================

@staff_bp.route("/schools")
@login_required
def schools():
    access_response = require_staff()

    if access_response:
        return access_response

    schools = (
        School.query
        .order_by(School.name.asc())
        .all()
    )

    return render_template(
        "staff/schools.html",
        schools=schools,
    )


# ============================================================================
# SCHOOL MANAGEMENT HUB
# ============================================================================


@staff_bp.route("/schools/<int:school_id>/manage")
@login_required
def manage_school(school_id):
    access_response = require_staff()

    if access_response:
        return access_response

    school = School.query.get_or_404(school_id)

    active_session = (
        AcademicSession.query
        .filter_by(
            school_id=school.id,
            active=True,
        )
        .first()
    )

    return render_template(
        "staff/school_management.html",
        school=school,
        active_session=active_session,
    )

@staff_bp.route("/schools/new", methods=["GET", "POST"])
@login_required
def new_school():
    access_response = require_staff()

    if access_response:
        return access_response

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        short_name = request.form.get("short_name", "").strip()
        address = request.form.get("address", "").strip()

        if not name:
            flash(
                "School name is required.",
                "danger",
            )

            return render_template(
                "staff/school_form.html",
                school=None,
            )

        existing = (
            School.query
            .filter_by(name=name)
            .first()
        )

        if existing:
            flash(
                "A school with this name already exists.",
                "warning",
            )

            return render_template(
                "staff/school_form.html",
                school=None,
            )

        school = School(
            name=name,
            short_name=short_name or None,
            address=address or None,
            active=True,
        )

        db.session.add(school)
        db.session.commit()

        flash(
            f"{school.name} was created successfully.",
            "success",
        )

        return redirect(
            url_for("staff.schools")
        )

    return render_template(
        "staff/school_form.html",
        school=None,
    )


@staff_bp.route(
    "/schools/<int:school_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_school(school_id):
    access_response = require_staff()

    if access_response:
        return access_response

    school = School.query.get_or_404(school_id)

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        short_name = request.form.get("short_name", "").strip()
        address = request.form.get("address", "").strip()

        if not name:
            flash(
                "School name is required.",
                "danger",
            )

            return render_template(
                "staff/school_form.html",
                school=school,
            )

        existing = (
            School.query
            .filter(
                School.name == name,
                School.id != school.id,
            )
            .first()
        )

        if existing:
            flash(
                "Another school with this name already exists.",
                "warning",
            )

            return render_template(
                "staff/school_form.html",
                school=school,
            )

        school.name = name
        school.short_name = short_name or None
        school.address = address or None

        db.session.commit()

        flash(
            f"{school.name} was updated successfully.",
            "success",
        )

        return redirect(
            url_for("staff.schools")
        )

    return render_template(
        "staff/school_form.html",
        school=school,
    )


@staff_bp.route(
    "/schools/<int:school_id>/toggle",
    methods=["POST"],
)
@login_required
def toggle_school(school_id):
    access_response = require_staff()

    if access_response:
        return access_response

    school = School.query.get_or_404(school_id)

    school.active = not school.active

    db.session.commit()

    status = (
        "activated"
        if school.active
        else "deactivated"
    )

    flash(
        f"{school.name} was {status}.",
        "success",
    )

    return redirect(
        url_for("staff.schools")
    )


# ============================================================================
# ACADEMIC SESSION MANAGEMENT
# ============================================================================

def get_school_session(school_id, session_id):
    """
    Return an AcademicSession belonging to the specified School.
    """

    school = School.query.get_or_404(school_id)

    academic_session = (
        AcademicSession.query
        .filter_by(
            id=session_id,
            school_id=school.id,
        )
        .first_or_404()
    )

    return school, academic_session


@staff_bp.route(
    "/schools/<int:school_id>/sessions"
)
@login_required
def school_sessions(school_id):
    access_response = require_staff()

    if access_response:
        return access_response

    school = School.query.get_or_404(school_id)

    sessions = (
        AcademicSession.query
        .filter_by(school_id=school.id)
        .order_by(
            AcademicSession.start_date.desc(),
            AcademicSession.name.asc(),
        )
        .all()
    )

    return render_template(
        "staff/sessions.html",
        school=school,
        sessions=sessions,
    )


@staff_bp.route(
    "/schools/<int:school_id>/sessions/new",
    methods=["GET", "POST"],
)
@login_required
def new_session(school_id):
    access_response = require_staff()

    if access_response:
        return access_response

    school = School.query.get_or_404(school_id)

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        start_date_raw = request.form.get(
            "start_date",
            "",
        ).strip()
        end_date_raw = request.form.get(
            "end_date",
            "",
        ).strip()
        active = request.form.get("active") == "on"

        if not name:
            flash(
                "Academic session name is required.",
                "danger",
            )

            return render_template(
                "staff/session_form.html",
                school=school,
                session=None,
            )

        existing = (
            AcademicSession.query
            .filter_by(
                school_id=school.id,
                name=name,
            )
            .first()
        )

        if existing:
            flash(
                "An academic session with this name already "
                "exists in this school.",
                "warning",
            )

            return render_template(
                "staff/session_form.html",
                school=school,
                session=None,
            )

        start_date = parse_date(
            start_date_raw,
            "Start date",
        )

        if start_date_raw and start_date is None:
            return render_template(
                "staff/session_form.html",
                school=school,
                session=None,
            )

        end_date = parse_date(
            end_date_raw,
            "End date",
        )

        if end_date_raw and end_date is None:
            return render_template(
                "staff/session_form.html",
                school=school,
                session=None,
            )

        if (
            start_date
            and end_date
            and end_date < start_date
        ):
            flash(
                "End date cannot be earlier than the start date.",
                "danger",
            )

            return render_template(
                "staff/session_form.html",
                school=school,
                session=None,
            )

        if active:
            deactivate_other_sessions(
                school.id
            )

        academic_session = AcademicSession(
            school_id=school.id,
            name=name,
            start_date=start_date,
            end_date=end_date,
            active=active,
        )

        db.session.add(academic_session)
        db.session.commit()

        flash(
            f"{academic_session.name} was created successfully.",
            "success",
        )

        return redirect(
            url_for(
                "staff.school_sessions",
                school_id=school.id,
            )
        )

    return render_template(
        "staff/session_form.html",
        school=school,
        session=None,
    )


@staff_bp.route(
    "/schools/<int:school_id>/sessions/<int:session_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_session(school_id, session_id):
    access_response = require_staff()

    if access_response:
        return access_response

    school, academic_session = get_school_session(
        school_id,
        session_id,
    )

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        start_date_raw = request.form.get(
            "start_date",
            "",
        ).strip()
        end_date_raw = request.form.get(
            "end_date",
            "",
        ).strip()
        active = request.form.get("active") == "on"

        if not name:
            flash(
                "Academic session name is required.",
                "danger",
            )

            return render_template(
                "staff/session_form.html",
                school=school,
                session=academic_session,
            )

        existing = (
            AcademicSession.query
            .filter(
                AcademicSession.school_id == school.id,
                AcademicSession.name == name,
                AcademicSession.id != academic_session.id,
            )
            .first()
        )

        if existing:
            flash(
                "Another academic session with this name "
                "already exists in this school.",
                "warning",
            )

            return render_template(
                "staff/session_form.html",
                school=school,
                session=academic_session,
            )

        start_date = parse_date(
            start_date_raw,
            "Start date",
        )

        if start_date_raw and start_date is None:
            return render_template(
                "staff/session_form.html",
                school=school,
                session=academic_session,
            )

        end_date = parse_date(
            end_date_raw,
            "End date",
        )

        if end_date_raw and end_date is None:
            return render_template(
                "staff/session_form.html",
                school=school,
                session=academic_session,
            )

        if (
            start_date
            and end_date
            and end_date < start_date
        ):
            flash(
                "End date cannot be earlier than the start date.",
                "danger",
            )

            return render_template(
                "staff/session_form.html",
                school=school,
                session=academic_session,
            )

        if active:
            deactivate_other_sessions(
                school.id,
                exclude_id=academic_session.id,
            )

        academic_session.name = name
        academic_session.start_date = start_date
        academic_session.end_date = end_date
        academic_session.active = active

        db.session.commit()

        flash(
            f"{academic_session.name} was updated successfully.",
            "success",
        )

        return redirect(
            url_for(
                "staff.school_sessions",
                school_id=school.id,
            )
        )

    return render_template(
        "staff/session_form.html",
        school=school,
        session=academic_session,
    )


@staff_bp.route(
    "/schools/<int:school_id>/sessions/<int:session_id>/toggle",
    methods=["POST"],
)
@login_required
def toggle_session(school_id, session_id):
    access_response = require_staff()

    if access_response:
        return access_response

    school, academic_session = get_school_session(
        school_id,
        session_id,
    )

    if academic_session.active:

        academic_session.active = False

        flash(
            f"{academic_session.name} was deactivated.",
            "success",
        )

    else:

        deactivate_other_sessions(
            school.id,
            exclude_id=academic_session.id,
        )

        academic_session.active = True

        flash(
            f"{academic_session.name} is now the active "
            "academic session.",
            "success",
        )

    db.session.commit()

    return redirect(
        url_for(
            "staff.school_sessions",
            school_id=school.id,
        )
    )


def parse_date(value, field_name):
    """
    Convert YYYY-MM-DD form input into a date.
    Returns None when empty or invalid.
    """

    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    except ValueError:

        flash(
            f"{field_name} must be a valid date.",
            "danger",
        )

        return None


def deactivate_other_sessions(
    school_id,
    exclude_id=None,
):
    """
    Ensure that at most one academic session is active
    for a school.
    """

    query = (
        AcademicSession.query
        .filter(
            AcademicSession.school_id == school_id,
            AcademicSession.active.is_(True),
        )
    )

    if exclude_id is not None:
        query = query.filter(
            AcademicSession.id != exclude_id
        )

    query.update(
        {"active": False},
        synchronize_session=False,
    )


# ============================================================================
# CLASS MANAGEMENT
# ============================================================================

def get_school_class(
    school_id,
    class_id,
):
    """
    Return a SchoolClass belonging to the specified school.
    """

    school = School.query.get_or_404(
        school_id
    )

    school_class = (
        SchoolClass.query
        .filter_by(
            id=class_id,
            school_id=school.id,
        )
        .first_or_404()
    )

    return school, school_class


@staff_bp.route(
    "/schools/<int:school_id>/sessions/<int:session_id>/classes"
)
@login_required
def school_classes(
    school_id,
    session_id,
):
    access_response = require_staff()

    if access_response:
        return access_response

    school, academic_session = get_school_session(
        school_id,
        session_id,
    )

    classes = (
        SchoolClass.query
        .filter_by(
            school_id=school.id,
        )
        .order_by(
            SchoolClass.display_order.asc(),
            SchoolClass.name.asc(),
        )
        .all()
    )

    return render_template(
        "staff/classes.html",
        school=school,
        session=academic_session,
        classes=classes,
    )


@staff_bp.route(
    "/schools/<int:school_id>/sessions/<int:session_id>/classes/new",
    methods=["GET", "POST"],
)
@login_required
def new_class(
    school_id,
    session_id,
):
    access_response = require_staff()

    if access_response:
        return access_response

    school, academic_session = get_school_session(
        school_id,
        session_id,
    )

    if request.method == "POST":

        name = request.form.get(
            "name",
            "",
        ).strip()

        display_order_raw = request.form.get(
            "display_order",
            "0",
        ).strip()

        if not name:
            flash(
                "Class name is required.",
                "danger",
            )

            return render_template(
                "staff/class_form.html",
                school=school,
                session=academic_session,
                school_class=None,
            )

        try:
            display_order = int(
                display_order_raw or 0
            )

        except ValueError:

            flash(
                "Display order must be a whole number.",
                "danger",
            )

            return render_template(
                "staff/class_form.html",
                school=school,
                session=academic_session,
                school_class=None,
            )

        existing = (
            SchoolClass.query
            .filter_by(
                school_id=school.id,
                name=name,
            )
            .first()
        )

        if existing:
            flash(
                "A class with this name already exists "
                "in this school.",
                "warning",
            )

            return render_template(
                "staff/class_form.html",
                school=school,
                session=academic_session,
                school_class=None,
            )

        school_class = SchoolClass(
            school_id=school.id,
            name=name,
            display_order=display_order,
            active=True,
        )

        db.session.add(school_class)
        db.session.commit()

        flash(
            f"{school_class.name} was created successfully.",
            "success",
        )

        return redirect(
            url_for(
                "staff.school_classes",
                school_id=school.id,
                session_id=academic_session.id,
            )
        )

    return render_template(
        "staff/class_form.html",
        school=school,
        session=academic_session,
        school_class=None,
    )


@staff_bp.route(
    "/schools/<int:school_id>/sessions/<int:session_id>/classes/<int:class_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_class(
    school_id,
    session_id,
    class_id,
):
    access_response = require_staff()

    if access_response:
        return access_response

    school, academic_session = get_school_session(
        school_id,
        session_id,
    )

    school_class = (
        SchoolClass.query
        .filter_by(
            id=class_id,
            school_id=school.id,
        )
        .first_or_404()
    )

    if request.method == "POST":

        name = request.form.get(
            "name",
            "",
        ).strip()

        display_order_raw = request.form.get(
            "display_order",
            "0",
        ).strip()

        if not name:
            flash(
                "Class name is required.",
                "danger",
            )

            return render_template(
                "staff/class_form.html",
                school=school,
                session=academic_session,
                school_class=school_class,
            )

        try:
            display_order = int(
                display_order_raw or 0
            )

        except ValueError:

            flash(
                "Display order must be a whole number.",
                "danger",
            )

            return render_template(
                "staff/class_form.html",
                school=school,
                session=academic_session,
                school_class=school_class,
            )

        existing = (
            SchoolClass.query
            .filter(
                SchoolClass.school_id == school.id,
                SchoolClass.name == name,
                SchoolClass.id != school_class.id,
            )
            .first()
        )

        if existing:
            flash(
                "Another class with this name already exists.",
                "warning",
            )

            return render_template(
                "staff/class_form.html",
                school=school,
                session=academic_session,
                school_class=school_class,
            )

        school_class.name = name
        school_class.display_order = display_order

        db.session.commit()

        flash(
            f"{school_class.name} was updated successfully.",
            "success",
        )

        return redirect(
            url_for(
                "staff.school_classes",
                school_id=school.id,
                session_id=academic_session.id,
            )
        )

    return render_template(
        "staff/class_form.html",
        school=school,
        session=academic_session,
        school_class=school_class,
    )


@staff_bp.route(
    "/schools/<int:school_id>/sessions/<int:session_id>/classes/<int:class_id>/toggle",
    methods=["POST"],
)
@login_required
def toggle_class(
    school_id,
    session_id,
    class_id,
):
    access_response = require_staff()

    if access_response:
        return access_response

    school, academic_session = get_school_session(
        school_id,
        session_id,
    )

    school_class = (
        SchoolClass.query
        .filter_by(
            id=class_id,
            school_id=school.id,
        )
        .first_or_404()
    )

    school_class.active = not school_class.active

    db.session.commit()

    status = (
        "activated"
        if school_class.active
        else "deactivated"
    )

    flash(
        f"{school_class.name} was {status}.",
        "success",
    )

    return redirect(
        url_for(
            "staff.school_classes",
            school_id=school.id,
            session_id=academic_session.id,
        )
    )


# ============================================================================
# CLASS GROUP MANAGEMENT
# ============================================================================

def get_class_context(
    school_id,
    session_id,
    class_id,
):
    """
    Return School, AcademicSession and SchoolClass after
    validating the complete hierarchy.
    """

    school, academic_session = get_school_session(
        school_id,
        session_id,
    )

    school_class = (
        SchoolClass.query
        .filter_by(
            id=class_id,
            school_id=school.id,
        )
        .first_or_404()
    )

    return (
        school,
        academic_session,
        school_class,
    )


@staff_bp.route(
    "/schools/<int:school_id>/sessions/<int:session_id>/classes/<int:class_id>/groups"
)
@login_required
def class_groups(
    school_id,
    session_id,
    class_id,
):
    access_response = require_staff()

    if access_response:
        return access_response

    (
        school,
        academic_session,
        school_class,
    ) = get_class_context(
        school_id,
        session_id,
        class_id,
    )

    groups = (
        ClassGroup.query
        .filter_by(
            class_id=school_class.id,
        )
        .order_by(
            ClassGroup.display_order.asc(),
            ClassGroup.name.asc(),
        )
        .all()
    )

    return render_template(
        "staff/class_groups.html",
        school=school,
        session=academic_session,
        school_class=school_class,
        groups=groups,
    )


@staff_bp.route(
    "/schools/<int:school_id>/sessions/<int:session_id>/classes/<int:class_id>/groups/new",
    methods=["GET", "POST"],
)
@login_required
def new_class_group(
    school_id,
    session_id,
    class_id,
):
    access_response = require_staff()

    if access_response:
        return access_response

    (
        school,
        academic_session,
        school_class,
    ) = get_class_context(
        school_id,
        session_id,
        class_id,
    )

    categories = (
        SubjectCategory.query
        .filter_by(
            school_id=school.id,
            active=True,
        )
        .order_by(
            SubjectCategory.name.asc(),
        )
        .all()
    )

    if request.method == "POST":

        name = request.form.get(
            "name",
            "",
        ).strip()

        display_order_raw = request.form.get(
            "display_order",
            "0",
        ).strip()

        category_id = request.form.get(
            "category_id",
            type=int,
        )

        if not name:
            flash(
                "Class group name is required.",
                "danger",
            )

            return render_template(
                "staff/class_group_form.html",
                school=school,
                session=academic_session,
                school_class=school_class,
                group=None,
                categories=categories,
            )

        try:
            display_order = int(
                display_order_raw or 0
            )

        except ValueError:

            flash(
                "Display order must be a whole number.",
                "danger",
            )

            return render_template(
                "staff/class_group_form.html",
                school=school,
                session=academic_session,
                school_class=school_class,
                group=None,
                categories=categories,
            )

        existing = (
            ClassGroup.query
            .filter_by(
                class_id=school_class.id,
                name=name,
            )
            .first()
        )

        if existing:
            flash(
                "A group with this name already exists "
                "in this class.",
                "warning",
            )

            return render_template(
                "staff/class_group_form.html",
                school=school,
                session=academic_session,
                school_class=school_class,
                group=None,
                categories=categories,
            )

        category = None

        if category_id:
            category = (
                SubjectCategory.query
                .filter_by(
                    id=category_id,
                    school_id=school.id,
                    active=True,
                )
                .first()
            )

            if not category:
                flash(
                    "The selected category is invalid.",
                    "danger",
                )

                return render_template(
                    "staff/class_group_form.html",
                    school=school,
                    session=academic_session,
                    school_class=school_class,
                    group=None,
                    categories=categories,
                )

        group = ClassGroup(
            class_id=school_class.id,
            name=name,
            display_order=display_order,
            category_id=category.id if category else None,
            active=True,
        )

        db.session.add(group)
        db.session.commit()

        flash(
            f"{group.name} was created successfully.",
            "success",
        )

        return redirect(
            url_for(
                "staff.class_groups",
                school_id=school.id,
                session_id=academic_session.id,
                class_id=school_class.id,
            )
        )

    return render_template(
        "staff/class_group_form.html",
        school=school,
        session=academic_session,
        school_class=school_class,
        group=None,
        categories=categories,
    )


@staff_bp.route(
    "/schools/<int:school_id>/sessions/<int:session_id>/classes/<int:class_id>/groups/<int:group_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_class_group(
    school_id,
    session_id,
    class_id,
    group_id,
):
    access_response = require_staff()

    if access_response:
        return access_response

    (
        school,
        academic_session,
        school_class,
    ) = get_class_context(
        school_id,
        session_id,
        class_id,
    )

    group = (
        ClassGroup.query
        .filter_by(
            id=group_id,
            class_id=school_class.id,
        )
        .first_or_404()
    )

    # ---------------------------------------------------------------
    # LOAD ACTIVE + CURRENT CATEGORY OPTIONS
    # ---------------------------------------------------------------

    categories = (
        SubjectCategory.query
        .filter(
            SubjectCategory.school_id == school.id,
            db.or_(
                SubjectCategory.active.is_(True),
                SubjectCategory.id == group.category_id,
            ),
        )
        .order_by(
            SubjectCategory.name.asc(),
        )
        .all()
    )

    # ---------------------------------------------------------------
    # SAVE
    # ---------------------------------------------------------------

    if request.method == "POST":

        name = request.form.get(
            "name",
            "",
        ).strip()

        display_order_raw = request.form.get(
            "display_order",
            "0",
        ).strip()

        category_id = request.form.get(
            "category_id",
            type=int,
        )

        if not name:

            flash(
                "Class group name is required.",
                "danger",
            )

            return render_template(
                "staff/class_group_form.html",
                school=school,
                session=academic_session,
                school_class=school_class,
                group=group,
                categories=categories,
            )

        try:

            display_order = int(
                display_order_raw or 0
            )

        except ValueError:

            flash(
                "Display order must be a whole number.",
                "danger",
            )

            return render_template(
                "staff/class_group_form.html",
                school=school,
                session=academic_session,
                school_class=school_class,
                group=group,
                categories=categories,
            )

        existing = (
            ClassGroup.query
            .filter(
                ClassGroup.class_id == school_class.id,
                ClassGroup.name == name,
                ClassGroup.id != group.id,
            )
            .first()
        )

        if existing:

            flash(
                "Another group with this name already exists "
                "in this class.",
                "warning",
            )

            return render_template(
                "staff/class_group_form.html",
                school=school,
                session=academic_session,
                school_class=school_class,
                group=group,
                categories=categories,
            )

        # -----------------------------------------------------------
        # VALIDATE CATEGORY
        # -----------------------------------------------------------

        category = None

        if category_id:

            category = (
                SubjectCategory.query
                .filter_by(
                    id=category_id,
                    school_id=school.id,
                )
                .first()
            )

            if not category:

                flash(
                    "The selected category is invalid.",
                    "danger",
                )

                return render_template(
                    "staff/class_group_form.html",
                    school=school,
                    session=academic_session,
                    school_class=school_class,
                    group=group,
                    categories=categories,
                )

        # -----------------------------------------------------------
        # UPDATE
        # -----------------------------------------------------------

        group.name = name
        group.display_order = display_order
        group.category_id = (
            category.id
            if category
            else None
        )

        db.session.commit()

        flash(
            f"{group.name} was updated successfully.",
            "success",
        )

        return redirect(
            url_for(
                "staff.class_groups",
                school_id=school.id,
                session_id=academic_session.id,
                class_id=school_class.id,
            )
        )

    # ---------------------------------------------------------------
    # DISPLAY FORM
    # ---------------------------------------------------------------

    return render_template(
        "staff/class_group_form.html",
        school=school,
        session=academic_session,
        school_class=school_class,
        group=group,
        categories=categories,
    )


@staff_bp.route(
    "/schools/<int:school_id>/sessions/<int:session_id>/classes/<int:class_id>/groups/<int:group_id>/toggle",
    methods=["POST"],
)
@login_required
def toggle_class_group(
    school_id,
    session_id,
    class_id,
    group_id,
):
    access_response = require_staff()

    if access_response:
        return access_response

    (
        school,
        academic_session,
        school_class,
    ) = get_class_context(
        school_id,
        session_id,
        class_id,
    )

    group = (
        ClassGroup.query
        .filter_by(
            id=group_id,
            class_id=school_class.id,
        )
        .first_or_404()
    )

    group.active = not group.active

    db.session.commit()

    status = (
        "activated"
        if group.active
        else "deactivated"
    )

    flash(
        f"{group.name} was {status}.",
        "success",
    )

    return redirect(
        url_for(
            "staff.class_groups",
            school_id=school.id,
            session_id=academic_session.id,
            class_id=school_class.id,
        )
    )

# ============================================================================
# SUBJECT CATEGORY MANAGEMENT
# ============================================================================


@staff_bp.route(
    "/schools/<int:school_id>/subject-categories",
    methods=["GET"],
)
@login_required
def subject_categories(school_id):
    """List subject categories belonging to a school."""

    access_response = require_staff()

    if access_response:
        return access_response

    school = School.query.get_or_404(school_id)

    categories = (
        SubjectCategory.query
        .filter_by(
            school_id=school.id,
        )
        .order_by(
            SubjectCategory.name.asc(),
        )
        .all()
    )

    return render_template(
        "staff/subject_categories.html",
        school=school,
        categories=categories,
    )


@staff_bp.route(
    "/schools/<int:school_id>/subject-categories/new",
    methods=["GET", "POST"],
)
@login_required
def new_subject_category(school_id):
    """Create a subject category for a school."""

    access_response = require_staff()

    if access_response:
        return access_response

    school = School.query.get_or_404(school_id)

    if request.method == "POST":

        name = request.form.get(
            "name",
            "",
        ).strip()

        description = request.form.get(
            "description",
            "",
        ).strip()

        if not name:
            flash(
                "Category name is required.",
                "danger",
            )

            return render_template(
                "staff/subject_category_form.html",
                school=school,
                category=None,
                edit_mode=False,
            )

        existing = (
            SubjectCategory.query
            .filter(
                SubjectCategory.school_id == school.id,
                db.func.lower(SubjectCategory.name) == name.lower(),
            )
            .first()
        )

        if existing:
            flash(
                "A category with this name already exists in this school.",
                "warning",
            )

            return render_template(
                "staff/subject_category_form.html",
                school=school,
                category=None,
                edit_mode=False,
            )

        category = SubjectCategory(
            school_id=school.id,
            name=name,
            description=description or None,
            active=True,
        )

        db.session.add(category)
        db.session.commit()

        flash(
            f"Category '{category.name}' created successfully.",
            "success",
        )

        return redirect(
            url_for(
                "staff.subject_categories",
                school_id=school.id,
            )
        )

    return render_template(
        "staff/subject_category_form.html",
        school=school,
        category=None,
        edit_mode=False,
    )


@staff_bp.route(
    "/schools/<int:school_id>/subject-categories/<int:category_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_subject_category(
    school_id,
    category_id,
):
    """Edit a school subject category."""

    access_response = require_staff()

    if access_response:
        return access_response

    school = School.query.get_or_404(school_id)

    category = (
        SubjectCategory.query
        .filter_by(
            id=category_id,
            school_id=school.id,
        )
        .first_or_404()
    )

    if request.method == "POST":

        name = request.form.get(
            "name",
            "",
        ).strip()

        description = request.form.get(
            "description",
            "",
        ).strip()

        if not name:
            flash(
                "Category name is required.",
                "danger",
            )

            return render_template(
                "staff/subject_category_form.html",
                school=school,
                category=category,
                edit_mode=True,
            )

        existing = (
            SubjectCategory.query
            .filter(
                SubjectCategory.school_id == school.id,
                SubjectCategory.id != category.id,
                db.func.lower(SubjectCategory.name) == name.lower(),
            )
            .first()
        )

        if existing:
            flash(
                "Another category with this name already exists "
                "in this school.",
                "warning",
            )

            return render_template(
                "staff/subject_category_form.html",
                school=school,
                category=category,
                edit_mode=True,
            )

        category.name = name
        category.description = description or None

        db.session.commit()

        flash(
            f"Category '{category.name}' updated successfully.",
            "success",
        )

        return redirect(
            url_for(
                "staff.subject_categories",
                school_id=school.id,
            )
        )

    return render_template(
        "staff/subject_category_form.html",
        school=school,
        category=category,
        edit_mode=True,
    )


@staff_bp.route(
    "/schools/<int:school_id>/subject-categories/<int:category_id>/toggle",
    methods=["POST"],
)
@login_required
def toggle_subject_category(
    school_id,
    category_id,
):
    """Activate or deactivate a school subject category."""

    access_response = require_staff()

    if access_response:
        return access_response

    school = School.query.get_or_404(school_id)

    category = (
        SubjectCategory.query
        .filter_by(
            id=category_id,
            school_id=school.id,
        )
        .first_or_404()
    )

    category.active = not category.active

    db.session.commit()

    status = (
        "activated"
        if category.active
        else "deactivated"
    )

    flash(
        f"Category '{category.name}' {status}.",
        "success",
    )

    return redirect(
        url_for(
            "staff.subject_categories",
            school_id=school.id,
        )
    )

# ============================================================================
# SUBJECT MANAGEMENT
# ============================================================================

@staff_bp.route(
    "/schools/<int:school_id>/subjects",
    methods=["GET"],
)
@login_required
def subjects(school_id):
    """List subjects belonging to a school."""

    require_staff()

    school = School.query.get_or_404(school_id)

    subjects = (
        SchoolSubject.query
        .filter_by(school_id=school.id)
        .order_by(SchoolSubject.name.asc())
        .all()
    )

    return render_template(
        "staff/subjects.html",
        school=school,
        subjects=subjects,
    )


@staff_bp.route(
    "/schools/<int:school_id>/subjects/new",
    methods=["GET", "POST"],
)
@login_required
def new_subject(school_id):
    """Create a subject for a school."""

    require_staff()

    school = School.query.get_or_404(school_id)

    categories = (
        SubjectCategory.query
        .filter_by(
            school_id=school.id,
            active=True,
        )
        .order_by(
            SubjectCategory.name.asc(),
        )
        .all()
    )

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        category_id = request.form.get(
            "category_id",
            type=int,
        )

        if not name:
            flash(
                "Subject name is required.",
                "danger",
            )

            return render_template(
                "staff/subject_form.html",
                school=school,
                subject=None,
                categories=categories,
                edit_mode=False,
            )

        existing = (
            SchoolSubject.query
            .filter(
                SchoolSubject.school_id == school.id,
                db.func.lower(SchoolSubject.name) == name.lower(),
            )
            .first()
        )

        if existing:
            flash(
                "A subject with this name already exists in this school.",
                "warning",
            )

            return render_template(
                "staff/subject_form.html",
                school=school,
                subject=None,
                categories=categories,
                edit_mode=False,
            )

        category = None

        if category_id:
            category = (
                SubjectCategory.query
                .filter_by(
                    id=category_id,
                    school_id=school.id,
                    active=True,
                )
                .first()
            )

            if not category:
                flash(
                    "The selected subject category is invalid.",
                    "danger",
                )

                return render_template(
                    "staff/subject_form.html",
                    school=school,
                    subject=None,
                    categories=categories,
                    edit_mode=False,
                )

        subject = SchoolSubject(
            school_id=school.id,
            name=name,
            code=code or None,
            category_id=category.id if category else None,
            active=True,
        )

        db.session.add(subject)
        db.session.commit()

        flash(
            f"Subject '{subject.name}' created successfully.",
            "success",
        )

        return redirect(
            url_for(
                "staff.subjects",
                school_id=school.id,
            )
        )

    return render_template(
        "staff/subject_form.html",
        school=school,
        subject=None,
        categories=categories,
        edit_mode=False,
    )

@staff_bp.route(
    "/schools/<int:school_id>/subjects/<int:subject_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_subject(school_id, subject_id):
    """Edit a school subject."""

    require_staff()

    school = School.query.get_or_404(school_id)

    subject = (
        SchoolSubject.query
        .filter_by(
            id=subject_id,
            school_id=school.id,
        )
        .first_or_404()
    )

    categories = (
        SubjectCategory.query
        .filter_by(
            school_id=school.id,
        )
        .order_by(
            SubjectCategory.name.asc(),
        )
        .all()
    )

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        category_id = request.form.get(
            "category_id",
            type=int,
        )

        if not name:
            flash(
                "Subject name is required.",
                "danger",
            )

            return render_template(
                "staff/subject_form.html",
                school=school,
                subject=subject,
                categories=categories,
                edit_mode=True,
            )

        existing = (
            SchoolSubject.query
            .filter(
                SchoolSubject.school_id == school.id,
                SchoolSubject.id != subject.id,
                db.func.lower(SchoolSubject.name) == name.lower(),
            )
            .first()
        )

        if existing:
            flash(
                "Another subject with this name already exists in this school.",
                "warning",
            )

            return render_template(
                "staff/subject_form.html",
                school=school,
                subject=subject,
                categories=categories,
                edit_mode=True,
            )

        category = None

        if category_id:
            category = (
                SubjectCategory.query
                .filter_by(
                    id=category_id,
                    school_id=school.id,
                )
                .first()
            )

            if not category:
                flash(
                    "The selected subject category is invalid.",
                    "danger",
                )

                return render_template(
                    "staff/subject_form.html",
                    school=school,
                    subject=subject,
                    categories=categories,
                    edit_mode=True,
                )

        subject.name = name
        subject.code = code or None
        subject.category_id = (
            category.id
            if category
            else None
        )

        db.session.commit()

        flash(
            f"Subject '{subject.name}' updated successfully.",
            "success",
        )

        return redirect(
            url_for(
                "staff.subjects",
                school_id=school.id,
            )
        )

    return render_template(
        "staff/subject_form.html",
        school=school,
        subject=subject,
        categories=categories,
        edit_mode=True,
    )

@staff_bp.route(
    "/schools/<int:school_id>/subjects/<int:subject_id>/toggle",
    methods=["POST"],
)
@login_required
def toggle_subject(school_id, subject_id):
    """Activate or deactivate a school subject."""

    require_staff()

    school = School.query.get_or_404(school_id)

    subject = (
        SchoolSubject.query
        .filter_by(
            id=subject_id,
            school_id=school.id,
        )
        .first_or_404()
    )

    subject.active = not subject.active

    db.session.commit()

    status = "activated" if subject.active else "deactivated"

    flash(
        f"Subject '{subject.name}' {status}.",
        "success",
    )

    return redirect(
        url_for(
            "staff.subjects",
            school_id=school.id,
        )
    )


# ============================================================================
# STUDENT MANAGEMENT
# ============================================================================

@staff_bp.route(
    "/students",
    methods=["GET"],
)
@login_required
def students():
    """List registered students for Staff management."""

    require_staff()

    students = (
        User.query
        .join(UserRole, UserRole.user_id == User.id)
        .filter(UserRole.role == "student")
        .order_by(User.username.asc())
        .all()
    )

    return render_template(
        "staff/students.html",
        students=students,
    )


@staff_bp.route("/subject-selections", methods=["GET"])
@login_required
def subject_selections():
    """List pending student subject-selection submissions for Staff review."""
    access_response = require_staff()
    if access_response:
        return access_response

    selections = (
        StudentSubjectSelection.query
        .filter(StudentSubjectSelection.status == "pending")
        .order_by(StudentSubjectSelection.submitted_at.desc())
        .all()
    )

    return render_template(
        "staff/subject_selections.html",
        selections=selections,
    )


@staff_bp.route("/subject-selections/<int:selection_id>", methods=["GET"])
@login_required
def subject_selection_review(selection_id):
    """Review an individual student subject-selection submission."""
    access_response = require_staff()
    if access_response:
        return access_response

    selection = StudentSubjectSelection.query.get_or_404(selection_id)

    return render_template(
        "staff/subject_selection_review.html",
        selection=selection,
    )

@staff_bp.route(
    "/subject-selections/<int:selection_id>/approve",
    methods=["POST"],
)
@login_required
def approve_subject_selection(selection_id):
    """Approve a student subject selection and create official enrollments."""
    access_response = require_staff()
    if access_response:
        return access_response

    selection = StudentSubjectSelection.query.get_or_404(selection_id)

    if selection.status != "pending":
        flash(
            "This subject selection has already been reviewed.",
            "warning",
        )
        return redirect(url_for("staff.subject_selection_review",
                                selection_id=selection.id))

    selected_subject_ids = {
        item.subject_id
        for item in selection.items
    }

    # Create or reactivate the official enrollments.
    for subject_id in selected_subject_ids:
        enrollment = (
            StudentSubjectEnrollment.query
            .filter_by(
                student_id=selection.student_id,
                school_id=selection.school_id,
                academic_session_id=selection.academic_session_id,
                class_id=selection.class_id,
                subject_id=subject_id,
            )
            .first()
        )

        if enrollment:
            enrollment.active = True
        else:
            enrollment = StudentSubjectEnrollment(
                student_id=selection.student_id,
                school_id=selection.school_id,
                academic_session_id=selection.academic_session_id,
                class_id=selection.class_id,
                class_group_id=selection.class_group_id,
                subject_id=subject_id,
                active=True,
                enrolled_at=datetime.utcnow(),
            )
            db.session.add(enrollment)

    selection.status = "approved"
    selection.reviewed_at = datetime.utcnow()
    selection.reviewed_by = current_user.id
    selection.review_note = None

    db.session.commit()

    flash(
        "Subject selection approved and official enrollments created.",
        "success",
    )

    return redirect(
        url_for(
            "staff.subject_selection_review",
            selection_id=selection.id,
        )
    )


@staff_bp.route(
    "/subject-selections/<int:selection_id>/reject",
    methods=["POST"],
)
@login_required
def reject_subject_selection(selection_id):
    """Reject a student subject selection and record the review reason."""
    access_response = require_staff()
    if access_response:
        return access_response

    selection = StudentSubjectSelection.query.get_or_404(selection_id)

    if selection.status != "pending":
        flash(
            "This subject selection has already been reviewed.",
            "warning",
        )
        return redirect(
            url_for(
                "staff.subject_selection_review",
                selection_id=selection.id,
            )
        )

    review_note = request.form.get("review_note", "").strip()

    if not review_note:
        flash(
            "Please provide a reason for rejecting the subject selection.",
            "danger",
        )
        return redirect(
            url_for(
                "staff.subject_selection_review",
                selection_id=selection.id,
            )
        )

    selection.status = "rejected"
    selection.reviewed_at = datetime.utcnow()
    selection.reviewed_by = current_user.id
    selection.review_note = review_note

    db.session.commit()

    flash(
        "Subject selection rejected. The student can submit a new selection.",
        "warning",
    )

    return redirect(
        url_for(
            "staff.subject_selection_review",
            selection_id=selection.id,
        )
    )


@staff_bp.route(
    "/students/<int:student_id>/placement",
    methods=["GET", "POST"],
)
@login_required
def student_placement(student_id):
    """Assign or update a student's school/session/class/group placement."""

    require_staff()

    student = (
        User.query
        .join(UserRole, UserRole.user_id == User.id)
        .filter(
            User.id == student_id,
            UserRole.role == "student",
        )
        .first_or_404()
    )

    schools = (
        School.query
        .filter_by(active=True)
        .order_by(School.name.asc())
        .all()
    )

    # ---------------------------------------------------------------
    # SAVE PLACEMENT
    # ---------------------------------------------------------------

    if request.method == "POST":

        school_id = request.form.get("school_id", type=int)
        session_id = request.form.get("academic_session_id", type=int)
        class_id = request.form.get("class_id", type=int)
        group_id = request.form.get("class_group_id", type=int)

        selected_school = None
        selected_session = None
        selected_class = None
        selected_group = None

        if school_id:
            selected_school = (
                School.query
                .filter_by(
                    id=school_id,
                    active=True,
                )
                .first()
            )

        if selected_school and session_id:
            selected_session = (
                AcademicSession.query
                .filter_by(
                    id=session_id,
                    school_id=selected_school.id,
                    active=True,
                )
                .first()
            )

        if selected_school and selected_session and class_id:
            selected_class = (
                SchoolClass.query
                .filter_by(
                    id=class_id,
                    school_id=selected_school.id,
                    active=True,
                )
                .first()
            )

        if selected_class and group_id:
            selected_group = (
                ClassGroup.query
                .filter_by(
                    id=group_id,
                    class_id=selected_class.id,
                    active=True,
                )
                .first()
            )

        if not selected_school:
            flash(
                "Please select a valid school.",
                "danger",
            )

        elif not selected_session:
            flash(
                "Please select a valid academic session.",
                "danger",
            )

        elif not selected_class:
            flash(
                "Please select a valid class.",
                "danger",
            )

        elif group_id and not selected_group:
            flash(
                "The selected class group does not belong to the selected class.",
                "danger",
            )

        else:

            membership = (
                SchoolMembership.query
                .filter_by(
                    user_id=student.id,
                    school_id=selected_school.id,
                    academic_session_id=selected_session.id,
                )
                .first()
            )

            if membership is None:

                membership = SchoolMembership(
                    user_id=student.id,
                    school_id=selected_school.id,
                    academic_session_id=selected_session.id,
                    class_id=selected_class.id,
                    class_group_id=(
                        selected_group.id
                        if selected_group
                        else None
                    ),
                    membership_type="student",
                    active=True,
                )

                db.session.add(membership)

            else:

                membership.class_id = selected_class.id

                membership.class_group_id = (
                    selected_group.id
                    if selected_group
                    else None
                )

                membership.membership_type = "student"
                membership.active = True

            db.session.commit()

            display_class = selected_class.name

            if selected_group:
                display_class += selected_group.name

            flash(
                f"{student.username} has been placed in {display_class}.",
                "success",
            )

            return redirect(
                url_for("staff.students")
            )

    # ---------------------------------------------------------------
    # EXISTING PLACEMENT
    # ---------------------------------------------------------------

    current_membership = (
        SchoolMembership.query
        .filter_by(
            user_id=student.id,
            active=True,
        )
        .order_by(
            SchoolMembership.created_at.desc()
        )
        .first()
    )

    return render_template(
        "staff/student_placement.html",
        student=student,
        schools=schools,
        current_membership=current_membership,
    )

# ============================================================================
# STUDENT PLACEMENT - DYNAMIC OPTIONS
# ============================================================================

@staff_bp.route(
    "/students/placement/sessions",
    methods=["GET"],
)
@login_required
def placement_sessions():
    """Return active academic sessions for a school."""

    require_staff()

    school_id = request.args.get("school_id", type=int)

    if not school_id:
        return {"sessions": []}

    sessions = (
        AcademicSession.query
        .filter_by(
            school_id=school_id,
            active=True,
        )
        .order_by(
            AcademicSession.name.desc()
        )
        .all()
    )

    return {
        "sessions": [
            {
                "id": session.id,
                "name": session.name,
            }
            for session in sessions
        ]
    }


@staff_bp.route(
    "/students/placement/classes",
    methods=["GET"],
)
@login_required
def placement_classes():
    """Return active classes for a school."""

    require_staff()

    school_id = request.args.get("school_id", type=int)

    if not school_id:
        return {"classes": []}

    classes = (
        SchoolClass.query
        .filter_by(
            school_id=school_id,
            active=True,
        )
        .order_by(
            SchoolClass.display_order.asc(),
            SchoolClass.name.asc(),
        )
        .all()
    )

    return {
        "classes": [
            {
                "id": school_class.id,
                "name": school_class.name,
            }
            for school_class in classes
        ]
    }


@staff_bp.route(
    "/students/placement/groups",
    methods=["GET"],
)
@login_required
def placement_groups():
    """Return active groups for a class."""

    require_staff()

    class_id = request.args.get("class_id", type=int)

    if not class_id:
        return {"groups": []}

    groups = (
        ClassGroup.query
        .filter_by(
            class_id=class_id,
            active=True,
        )
        .order_by(
            ClassGroup.display_order.asc(),
            ClassGroup.name.asc(),
        )
        .all()
    )

    return {
        "groups": [
            {
                "id": group.id,
                "name": group.name,
            }
            for group in groups
        ]
    }

@staff_bp.route(
    "/schools/<int:school_id>/subject-categories/<int:category_id>/configure",
    methods=["GET", "POST"],
)
def configure_subject_category(school_id, category_id):
    require_staff()

    school = School.query.filter_by(
        id=school_id,
        active=True,
    ).first_or_404()

    category = (
        SubjectCategory.query
        .filter_by(
            id=category_id,
            school_id=school.id,
        )
        .first_or_404()
    )

    # Load all active subjects belonging to this category.
    subjects = (
        SchoolSubject.query
        .filter_by(
            school_id=school.id,
            category_id=category.id,
        )
        .filter(
            SchoolSubject.active.is_(True),
        )
        .all()
    )

    if request.method == "POST":

        # ---------------------------------------------------------
        # Save category rule
        # ---------------------------------------------------------

        required = request.form.get("required") == "1"

        minimum_subjects = request.form.get(
            "minimum_subjects",
            type=int,
        )

        maximum_raw = request.form.get(
            "maximum_subjects",
            "",
        ).strip()

        maximum_subjects = (
            int(maximum_raw)
            if maximum_raw
            else None
        )

        if minimum_subjects is None or minimum_subjects < 0:
            flash(
                "Minimum subjects must be zero or greater.",
                "danger",
            )
            return redirect(
                url_for(
                    "staff.configure_subject_category",
                    school_id=school.id,
                    category_id=category.id,
                )
            )

        if maximum_subjects is not None and maximum_subjects < 0:
            flash(
                "Maximum subjects cannot be negative.",
                "danger",
            )
            return redirect(
                url_for(
                    "staff.configure_subject_category",
                    school_id=school.id,
                    category_id=category.id,
                )
            )

        if (
            maximum_subjects is not None
            and maximum_subjects < minimum_subjects
        ):
            flash(
                "Maximum subjects cannot be less than minimum subjects.",
                "danger",
            )
            return redirect(
                url_for(
                    "staff.configure_subject_category",
                    school_id=school.id,
                    category_id=category.id,
                )
            )

        rule = CategoryRule.query.filter_by(
            school_id=school.id,
            category_id=category.id,
        ).first()

        if rule is None:
            rule = CategoryRule(
                school_id=school.id,
                category_id=category.id,
            )
            db.session.add(rule)

        rule.required = required
        rule.minimum_subjects = minimum_subjects
        rule.maximum_subjects = maximum_subjects
        rule.active = True

        # ---------------------------------------------------------
        # Save individual subject configurations
        # ---------------------------------------------------------

        for subject in subjects:

            required_subject = (
                request.form.get(
                    f"required_{subject.id}"
                ) == "1"
            )

            default_subject = (
                request.form.get(
                    f"default_{subject.id}"
                ) == "1"
            )

            selectable_subject = (
                request.form.get(
                    f"selectable_{subject.id}"
                ) == "1"
            )

            display_order = request.form.get(
                f"display_order_{subject.id}",
                type=int,
            )

            if display_order is None:
                display_order = 0

            if display_order < 0:
                display_order = 0

            # Required subjects are automatically included.
            # Therefore they are not student-selectable.
            if required_subject:
                selectable_subject = False
                default_subject = True

            config = CategorySubjectConfig.query.filter_by(
                school_id=school.id,
                category_id=category.id,
                subject_id=subject.id,
            ).first()

            if config is None:
                config = CategorySubjectConfig(
                    school_id=school.id,
                    category_id=category.id,
                    subject_id=subject.id,
                )
                db.session.add(config)

            config.required = required_subject
            config.is_default = default_subject
            config.selectable = selectable_subject
            config.display_order = display_order
            config.active = True

        db.session.commit()

        flash(
            f"{category.name} category configuration saved successfully.",
            "success",
        )

        return redirect(
            url_for(
                "staff.configure_subject_category",
                school_id=school.id,
                category_id=category.id,
            )
        )

    # -------------------------------------------------------------
    # Load existing configuration for display
    # -------------------------------------------------------------

    rule = CategoryRule.query.filter_by(
        school_id=school.id,
        category_id=category.id,
    ).first()

    subject_configs = {
        config.subject_id: config
        for config in CategorySubjectConfig.query.filter_by(
            school_id=school.id,
            category_id=category.id,
        ).all()
    }

    subjects.sort(
        key=lambda subject: (
            subject_configs.get(subject.id).display_order
            if subject_configs.get(subject.id)
            else 9999,
            subject.name.lower(),
        )
    )

    return render_template(
        "staff/subject_category_configure.html",
        school=school,
        category=category,
        rule=rule,
        subjects=subjects,
        subject_configs=subject_configs,
    )

# ============================================================================
# SCHOOL-WIDE SUBJECT SELECTION RULE
# ============================================================================


@staff_bp.route(
    "/schools/<int:school_id>/subject-selection-rule",
    methods=["GET", "POST"],
)
@login_required
def subject_selection_rule(school_id):
    """
    Configure the school-wide minimum and maximum number
    of subjects a student may select.
    """

    access_response = require_staff()

    if access_response:
        return access_response

    school = School.query.get_or_404(school_id)

    rule = SubjectSelectionRule.query.filter_by(
        school_id=school.id,
    ).first()

    if request.method == "POST":

        minimum_raw = request.form.get(
            "minimum_subjects",
            "",
        ).strip()

        maximum_raw = request.form.get(
            "maximum_subjects",
            "",
        ).strip()

        active = request.form.get("active") == "on"

        # ---------------------------------------------------------------
        # VALIDATE MINIMUM
        # ---------------------------------------------------------------

        try:
            minimum_subjects = int(minimum_raw)
        except ValueError:
            flash(
                "Minimum subjects must be a whole number.",
                "danger",
            )

            return render_template(
                "staff/subject_selection_rule.html",
                school=school,
                rule=rule,
            )

        if minimum_subjects < 0:
            flash(
                "Minimum subjects cannot be negative.",
                "danger",
            )

            return render_template(
                "staff/subject_selection_rule.html",
                school=school,
                rule=rule,
            )

        # ---------------------------------------------------------------
        # VALIDATE MAXIMUM
        # ---------------------------------------------------------------

        try:
            maximum_subjects = int(maximum_raw)
        except ValueError:
            flash(
                "Maximum subjects must be a whole number.",
                "danger",
            )

            return render_template(
                "staff/subject_selection_rule.html",
                school=school,
                rule=rule,
            )

        if maximum_subjects < 0:
            flash(
                "Maximum subjects cannot be negative.",
                "danger",
            )

            return render_template(
                "staff/subject_selection_rule.html",
                school=school,
                rule=rule,
            )

        if maximum_subjects < minimum_subjects:
            flash(
                "Maximum subjects cannot be less than "
                "minimum subjects.",
                "danger",
            )

            return render_template(
                "staff/subject_selection_rule.html",
                school=school,
                rule=rule,
            )

        # ---------------------------------------------------------------
        # CREATE OR UPDATE RULE
        # ---------------------------------------------------------------

        if rule is None:
            rule = SubjectSelectionRule(
                school_id=school.id,
            )

            db.session.add(rule)

        rule.minimum_subjects = minimum_subjects
        rule.maximum_subjects = maximum_subjects
        rule.active = active

        db.session.commit()

        flash(
            "School-wide subject selection rule saved successfully.",
            "success",
        )

        return redirect(
            url_for(
                "staff.subject_selection_rule",
                school_id=school.id,
            )
        )

    return render_template(
        "staff/subject_selection_rule.html",
        school=school,
        rule=rule,
    )