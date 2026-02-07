from flask import render_template, redirect, url_for, request
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user
from app.extensions import db
from app.models.user import User
from app.auth import auth_bp
from auth.forms import RegisterForm, LoginForm
from main import main_bp

@main_bp.route('/')
def index():
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    ref_code = request.args.get('ref')

    if form.validate_on_submit():
        referred_by = None
        if ref_code:
            ref_user = User.query.filter_by(referral_code=ref_code).first()
            if ref_user:
                referred_by = ref_user.id

        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            referred_by=referred_by
        )
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            return redirect(url_for('auth.login'))

    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
