from flask import render_template, redirect, url_for, session
from flask_login import login_required, current_user

from . import workspace_bp


@workspace_bp.route("/")
@login_required
def index():
    """
    Display the workspaces available to the logged-in user.

    Primary workspaces come from UserRole records.
    Staff is handled separately through User.is_staff.
    """

    workspaces = []

    # ----------------------------------------------------------
    # PRIMARY USER ROLES
    # ----------------------------------------------------------
    for user_role in current_user.roles:
        workspaces.append({
            "key": user_role.role,
            "name": {
                "civil_servant": "Civil Servant",
                "teacher": "Teacher",
                "student": "Student",
            }.get(
                user_role.role,
                user_role.role.replace("_", " ").title()
            ),
            "type": "role",
        })

    # ----------------------------------------------------------
    # STAFF WORKSPACE
    # ----------------------------------------------------------
    if current_user.is_staff:
        workspaces.append({
            "key": "staff",
            "name": "Staff",
            "type": "staff",
        })

    # ----------------------------------------------------------
    # NO WORKSPACE
    # ----------------------------------------------------------
    if not workspaces:
        return render_template(
            "workspace/no_workspace.html"
        )

    # ----------------------------------------------------------
    # ONE WORKSPACE
    # ----------------------------------------------------------
    if len(workspaces) == 1:
        session["workspace"] = workspaces[0]["key"]

        return redirect(
            url_for("workspace.redirect_workspace")
        )

    # ----------------------------------------------------------
    # MULTIPLE WORKSPACES
    # ----------------------------------------------------------
    return render_template(
        "workspace/select.html",
        workspaces=workspaces
    )


@workspace_bp.route("/switch/<workspace>")
@login_required
def switch_workspace(workspace):
    """
    Switch the currently active workspace without logging out.
    """

    allowed_workspaces = {
        role.role
        for role in current_user.roles
    }

    if current_user.is_staff:
        allowed_workspaces.add("staff")

    if workspace not in allowed_workspaces:
        return redirect(
            url_for("workspace.index")
        )

    session["workspace"] = workspace

    return redirect(
        url_for("workspace.redirect_workspace")
    )


@workspace_bp.route("/redirect")
@login_required
def redirect_workspace():
    """
    Send the user to the dashboard belonging to the
    currently selected workspace.
    """

    workspace = session.get("workspace")

    # ----------------------------------------------------------
    # CIVIL SERVANT
    # ----------------------------------------------------------
    if workspace == "civil_servant":
        return redirect(
            url_for("dashboard.index")
        )

    # ----------------------------------------------------------
    # TEACHER
    # ----------------------------------------------------------
    if workspace == "teacher":
        return redirect(
        url_for("teacher.dashboard")
        )

    # ----------------------------------------------------------
    # STUDENT
    # ----------------------------------------------------------
    if workspace == "student":
        return render_template(
            "workspace/coming_soon.html",
            workspace_name="Student"
        )

    # ----------------------------------------------------------
    # STAFF
    # ----------------------------------------------------------
    if workspace == "staff":
        return render_template(
            "workspace/coming_soon.html",
            workspace_name="Staff"
        )

    # ----------------------------------------------------------
    # NO VALID WORKSPACE
    # ----------------------------------------------------------
    return redirect(
        url_for("workspace.index")
    )