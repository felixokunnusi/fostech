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
from wtforms.fields import DateTimeLocalField


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

class AssessmentForm(FlaskForm):
    """
    Form for creating and editing an assessment.

    This form creates the assessment container only.
    Questions will be added in the next stage.
    """

    title = StringField(
        "Assessment Title",
        validators=[DataRequired()],
    )

    subject = StringField(
        "Subject",
        validators=[DataRequired()],
    )

    class_name = StringField(
        "Class",
        validators=[DataRequired()],
    )

    topic = StringField(
        "Topic",
        validators=[Optional()],
    )

    assessment_type = SelectField(
        "Assessment Type",
        choices=[
            ("mcq", "Multiple Choice"),
            ("short_answer", "Short Answer"),
            ("theory", "Theory / Essay"),
            ("mixed", "Mixed Assessment"),
        ],
        default="mixed",
        validators=[DataRequired()],
    )

    mode = SelectField(
    "Assessment Mode",
    choices=[
        ("practice", "Practice"),
        ("graded", "Graded"),
    ],
    default="practice",
    validators=[DataRequired()],
    )

    instructions = TextAreaField(
        "Instructions",
        validators=[Optional()],
    )

    start_at = DateTimeLocalField(
        "Start Date / Time",
        validators=[Optional()],
    )

    due_at = DateTimeLocalField(
        "Due Date / Time",
        validators=[Optional()],
    )

    submit = SubmitField(
        "Create Assessment"
    )

class AssessmentQuestionForm(FlaskForm):
    """
    Form for creating and editing an assessment question.
    """

    question_type = SelectField(
        "Question Type",
        choices=[
            ("mcq", "Multiple Choice"),
            ("short_answer", "Short Answer"),
            ("theory", "Theory / Essay"),
        ],
        default="mcq",
        validators=[DataRequired()],
    )

    question_text = TextAreaField(
        "Question",
        validators=[DataRequired()],
    )

    option_a = TextAreaField(
        "Option A",
        validators=[Optional()],
    )

    option_b = TextAreaField(
        "Option B",
        validators=[Optional()],
    )

    option_c = TextAreaField(
        "Option C",
        validators=[Optional()],
    )

    option_d = TextAreaField(
        "Option D",
        validators=[Optional()],
    )

    correct_answer = TextAreaField(
        "Correct Answer",
        validators=[Optional()],
    )

    marks = IntegerField(
        "Marks",
        validators=[
            DataRequired(),
            NumberRange(min=1, max=100),
        ],
        default=1,
    )

    explanation = TextAreaField(
        "Explanation",
        validators=[Optional()],
    )

    submit = SubmitField(
        "Save Question"
    )
class AssessmentAIGenerationForm(FlaskForm):
    """
    Form for generating assessment questions with AI.

    The assessment's subject, class, and topic are inherited from
    the selected assessment and are therefore not requested again.
    """

    number_of_questions = IntegerField(
        "Number of Questions",
        validators=[
            DataRequired(),
            NumberRange(min=1, max=100),
        ],
        default=10,
    )

    question_type = SelectField(
        "Question Type",
        choices=[
            ("mcq", "Multiple Choice"),
            ("short_answer", "Short Answer"),
            ("theory", "Theory / Essay"),
        ],
        default="mcq",
        validators=[DataRequired()],
    )

    difficulty = SelectField(
        "Difficulty",
        choices=[
            ("easy", "Easy"),
            ("medium", "Medium"),
            ("hard", "Hard"),
            ("mixed", "Mixed"),
        ],
        default="mixed",
        validators=[DataRequired()],
    )

    examination_relevance = SelectField(
        "Examination / Curriculum Relevance",
        choices=[
            ("", "None / General Curriculum"),
            ("WAEC", "WAEC"),
            ("NECO", "NECO"),
            ("JAMB", "JAMB"),
        ],
        default="",
        validators=[Optional()],
    )

    additional_instructions = TextAreaField(
        "Additional Instructions",
        validators=[Optional()],
    )

    submit = SubmitField(
        "Generate Questions with AI"
    )