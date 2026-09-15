from flask import Blueprint


workspace_bp = Blueprint(
    "workspace",
    __name__,
    url_prefix="/workspace"
)


from . import routes  # noqa: E402,F401