from flask import redirect, url_for, render_template, request, session
from flask_login import current_user
from . import main_bp

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    # Persist referral code across pages
    ref = request.args.get("ref")
    if ref:
        session["ref"] = ref  # store latest referral code
    else:
        ref = session.get("ref")  # reuse stored code if present

    return render_template("main/index.html", ref=ref)
