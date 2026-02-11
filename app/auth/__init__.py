from flask import Blueprint
from app.models.user import User
from app.extensions import login_manager

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

from . import routes  # noqa: E402,F401  (ensures routes are imported)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
