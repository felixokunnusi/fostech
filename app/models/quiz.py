from datetime import datetime
from app.extensions import db


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    questions = db.relationship("Question", backref="subject", lazy=True)


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # NEW: difficulty band key, e.g. "1-4", "confirmation"
    band = db.Column(db.String(20), nullable=False, index=True)

    text = db.Column(db.Text, nullable=False)

    # ✅ NEW
    question_type = db.Column(db.String(50), nullable=False, default="psr", index=True)
    explanation = db.Column(db.Text)  # optional

    choices = db.relationship(
        "Choice",
        backref="question",
        lazy=True,
        cascade="all, delete-orphan"
    )
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=True)



class Choice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)


class QuizSession(db.Model):
    __tablename__ = "quiz_session"
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # NEW: which band this attempt is for
    band = db.Column(db.String(20), nullable=False, index=True)

    # NEW: "trial" or "exam"
    mode = db.Column(db.String(10), nullable=False, default="trial")

    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)  # started_at + 40 mins for exam

    completed_at = db.Column(db.DateTime)
    is_submitted = db.Column(db.Boolean, default=False)

    score = db.Column(db.Integer)
    total_questions = db.Column(db.Integer)

    # NEW: store fixed question ids as CSV string: "12,55,9,..."
    question_ids_csv = db.Column(db.Text, nullable=False)

    answers = db.relationship(
        "UserAnswer",
        backref="session",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def get_question_ids(self):
        return [int(x) for x in self.question_ids_csv.split(",") if x.strip()]



class UserAnswer(db.Model):
    __tablename__ = "user_answer"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("quiz_session.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    choice_id = db.Column(db.Integer, db.ForeignKey("choice.id"), nullable=False)

    question = db.relationship("Question")
    choice = db.relationship("Choice")
