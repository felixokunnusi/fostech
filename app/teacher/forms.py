from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    NumberRange,
    Optional,
)


class LessonPlanForm(FlaskForm):
    """
    Form for creating a lesson-plan request.

    FCT-EMIS is currently the only available format and is therefore
    selected by default. Additional formats can be added later.
    """

    format_key = SelectField(
        "Lesson Plan Format",
        choices=[
            (
                "fct_emis",
                "FCT-EMIS Lesson Plan — Default"
            ),
        ],
        default="fct_emis",
        validators=[DataRequired()]
    )

    lesson_date = DateField(
        "Date",
        validators=[Optional()],
        format="%Y-%m-%d"
    )

    class_name = StringField(
        "Class",
        validators=[DataRequired()]
    )

    number_in_class = IntegerField(
        "No. in Class",
        validators=[
            Optional(),
            NumberRange(min=1, max=1000)
        ]
    )

    average_age = IntegerField(
        "Average Age",
        validators=[
            Optional(),
            NumberRange(min=3, max=100)
        ]
    )

    subject = StringField(
        "Subject",
        validators=[DataRequired()]
    )

    lesson_topic = StringField(
        "Lesson Topic",
        validators=[DataRequired()]
    )

    unit_topic = TextAreaField(
        "Unit Topic",
        validators=[Optional()]
    )

    start_time = StringField(
        "Start Time",
        validators=[Optional()]
    )

    end_time = StringField(
        "End Time",
        validators=[Optional()]
    )

    duration_minutes = IntegerField(
        "Duration (Minutes)",
        validators=[
            Optional(),
            NumberRange(min=1, max=600)
        ]
    )

    learning_materials = TextAreaField(
        "Learning Material(s)",
        validators=[Optional()]
    )

    curriculum = TextAreaField(
        "Curriculum / Syllabus Context",
        validators=[Optional()]
    )

    examination_relevance = SelectField(
        "Examination Relevance",
        choices=[
            ("", "None / Not Applicable"),
            ("WAEC", "WAEC"),
            ("NECO", "NECO"),
            ("JAMB", "JAMB"),
        ],
        default="",
        validators=[Optional()]
    )

    submit = SubmitField(
        "Continue"
    )