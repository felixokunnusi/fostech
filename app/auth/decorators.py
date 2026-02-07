from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

def email_verified_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))

        if not current_user.is_email_verified:
            flash("Please verify your email to continue.", "warning")
            return redirect(url_for("auth.confirm_email"))

        return f(*args, **kwargs)
    return decorated_function
