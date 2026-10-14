from flask import render_template, redirect, url_for, session
from flask_login import login_required, current_user

from . import workspace_bp


def get_allowed_workspaces():
    """Return the workspaces this user is authorized to access."""
    allowed = {role.role for role in current_user.roles}

    if current_user.is_staff:
        allowed.add("staff")

    return allowed


@workspace_bp.route("/")
@login_required
def index():
    """Display the workspaces available to the logged-in user."""
    workspaces = []

    role_names = {
        "civil_servant": "Civil Servant",
        "teacher": "Teacher",
        "student": "Student",
    }

    for role in current_user.roles:
        workspaces.append({
            "key": role.role,
            "name": role_names.get(
                role.role,
                role.role.replace("_", " ").title(),
            ),
            "type": "role",
        })

    if current_user.is_staff:
        workspaces.append({
            "key": "staff",
            "name": "Staff",
            "type": "staff",
        })

    if not workspaces:
        session.pop("workspace", None)
        return render_template("workspace/no_workspace.html")

    if len(workspaces) == 1:
        session["workspace"] = workspaces[0]["key"]
        return redirect(url_for("workspace.redirect_workspace"))

    if session.get("workspace") not in get_allowed_workspaces():
        session.pop("workspace", None)

    return render_template(
        "workspace/select.html",
        workspaces=workspaces,
    )


@workspace_bp.route("/switch/<workspace>")
@login_required
def switch_workspace(workspace):
    """Switch to an authorized workspace."""
    if workspace not in get_allowed_workspaces():
        return redirect(url_for("workspace.index"))

    session["workspace"] = workspace
    return redirect(url_for("workspace.redirect_workspace"))


@workspace_bp.route("/redirect")
@login_required
def redirect_workspace():
    """Redirect to the selected workspace after checking access."""
    workspace = session.get("workspace")

    if workspace not in get_allowed_workspaces():
        session.pop("workspace", None)
        return redirect(url_for("workspace.index"))

    destinations = {
        "civil_servant": "dashboard.index",
        "teacher": "teacher.dashboard",
        "student": "student.dashboard",
        "staff": "staff.dashboard",
    }

    endpoint = destinations.get(workspace)

    if endpoint:
        return redirect(url_for(endpoint))

    session.pop("workspace", None)
    return redirect(url_for("workspace.index"))
