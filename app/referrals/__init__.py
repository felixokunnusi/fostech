from flask import Blueprint
referral_bp = Blueprint("referrals", __name__, url_prefix="/referrals")

from . import routes  # noqa: E402,F401  (ensures routes are imported)