from flask import Blueprint

staff_bp = Blueprint(
    "staff",
    __name__,
    url_prefix="/staff",
)

from app.staff import routes_bkp  # noqa: E402,F401