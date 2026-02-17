from flask import Blueprint

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Import routes AFTER blueprint is created
from . import routes  # noqa

from . import withdrawals