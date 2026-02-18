from flask import Blueprint

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")

# ✅ IMPORTANT: import webhooks so decorators register
from . import webhooks  # noqa: E402,F401
