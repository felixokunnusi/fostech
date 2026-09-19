from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, NumberRange, Optional


class LessonPlanForm(FlaskForm):
    format_key = SelectField(
        "Lesson Plan Format",
        choices=[
            (
                "fct_emis",
                "FCT-EMIS Lesson Plan — Default",
            )
        ],
        default="fct_emis",
        validators=[DataRequired()],
    )

    lesson_date = DateField(
        "Date",
        validators=[Optional()],
        format="%Y-%m-%d",
    )

    class_name = StringField(
        "Class",
        validators=[DataRequired()],
    )

    number_in_class = IntegerField(
        "No. in Class",
        validators=[
            Optional(),
            NumberRange(min=1, max=1000),
        ],
    )

    average_age = IntegerField(
        "Average Age",
        validators=[
            Optional(),
            NumberRange(min=3, max=100),
        ],
    )

    subject = StringField(
        "Subject",
        validators=[DataRequired()],
    )

    lesson_topic = StringField(
        "Lesson Topic",
        validators=[DataRequired()],
    )

    unit_topic = TextAreaField(
        "Unit Topic",
        validators=[Optional()],
    )

    start_time = StringField(
        "Start Time",
        validators=[Optional()],
    )

    end_time = StringField(
        "End Time",
        validators=[Optional()],
    )

    duration_minutes = IntegerField(
        "Duration (Minutes)",
        validators=[
            Optional(),
            NumberRange(min=1, max=600),
        ],
    )

    learning_materials = TextAreaField(
        "Learning Material(s)",
        validators=[Optional()],
    )

    curriculum = TextAreaField(
        "Curriculum / Syllabus Context",
        validators=[Optional()],
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
        validators=[Optional()],
    )

    submit = SubmitField("Continue")


class GeneratedLessonPlanForm(FlaskForm):
    """
    Form for manually editing AI-generated lesson-plan content.

    This form edits the generated lesson content only.
    It does not modify the underlying lesson-plan details and
    does not trigger AI regeneration.
    """

    lesson_objectives = TextAreaField(
        "Lesson Objectives",
        validators=[Optional()],
    )

    prior_ideas_mode = StringField(
        "STEP I — Mode",
        validators=[Optional()],
    )

    prior_ideas_teacher_activities = TextAreaField(
        "STEP I — Teacher's Activities",
        validators=[Optional()],
    )

    prior_ideas_student_activities = TextAreaField(
        "STEP I — Students' Activities",
        validators=[Optional()],
    )

    exploration_mode = StringField(
        "STEP II — Mode",
        validators=[Optional()],
    )

    exploration_teacher_activities = TextAreaField(
        "STEP II — Teacher's Activities",
        validators=[Optional()],
    )

    exploration_student_activities = TextAreaField(
        "STEP II — Students' Activities",
        validators=[Optional()],
    )

    discussion_mode = StringField(
        "STEP III — Mode",
        validators=[Optional()],
    )

    discussion_teacher_activities = TextAreaField(
        "STEP III — Teacher's Activities",
        validators=[Optional()],
    )

    discussion_student_activities = TextAreaField(
        "STEP III — Students' Activities",
        validators=[Optional()],
    )

    application_mode = StringField(
        "STEP IV — Mode",
        validators=[Optional()],
    )

    application_teacher_activities = TextAreaField(
        "STEP IV — Teacher's Activities",
        validators=[Optional()],
    )

    application_student_activities = TextAreaField(
        "STEP IV — Students' Activities",
        validators=[Optional()],
    )

    evaluation_mode = StringField(
        "STEP V — Mode",
        validators=[Optional()],
    )

    evaluation_teacher_activities = TextAreaField(
        "STEP V — Teacher's Activities",
        validators=[Optional()],
    )

    evaluation_student_activities = TextAreaField(
        "STEP V — Students' Activities",
        validators=[Optional()],
    )

    references = TextAreaField(
        "References",
        validators=[Optional()],
    )

    home_task = TextAreaField(
        "Home Task",
        validators=[Optional()],
    )

    submit = SubmitField("Save Changes")