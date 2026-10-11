
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class ProfileCompletionForm(FlaskForm):
    first_name = StringField(
        "First Name",
        validators=[
            DataRequired(message="First name is required."),
            Length(max=80),
        ],
    )

    surname = StringField(
        "Surname",
        validators=[
            DataRequired(message="Surname is required."),
            Length(max=80),
        ],
    )

    other_name = StringField(
        "Other Name (Optional)",
        validators=[
            Optional(),
            Length(max=80),
        ],
    )

    submit = SubmitField("Save Profile")
