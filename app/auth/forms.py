from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length
from app.models import User


class RegisterForm(FlaskForm):
    username = StringField(
        'Username',
        validators=[DataRequired()]
    )

    email = StringField(
        'Email',
        validators=[DataRequired(), Email()]
    )

    password = PasswordField(
        'Password',
        validators=[DataRequired()]
    )

    user_type = SelectField(
        'Account Type',
        choices=[
            ('civil_servant', 'Civil Servant'),
            ('teacher', 'Teacher'),
            ('student', 'Student'),
        ],
        validators=[DataRequired()]
    )

    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    email = StringField(
        'Email',
        validators=[DataRequired(), Email()]
    )

    password = PasswordField(
        'Password',
        validators=[DataRequired()]
    )

    submit = SubmitField('Login')


class ConfirmEmailForm(FlaskForm):
    email = StringField(
        'Email Address',
        validators=[DataRequired(), Email()]
    )

    code = StringField(
        'Confirmation Code',
        validators=[DataRequired(), Length(min=6, max=6)]
    )

    submit = SubmitField('Verify Email')
