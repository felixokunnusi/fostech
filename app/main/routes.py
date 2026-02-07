from flask import redirect, url_for, render_template
from flask_login import current_user
from . import main_bp

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))
