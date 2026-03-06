from datetime import datetime
from app.extensions import db


class CampaignLog(db.Model):
    __tablename__ = "campaign_logs"

    id = db.Column(db.Integer, primary_key=True)

    # who triggered it (admin)
    created_by_user_id = db.Column(db.Integer, nullable=True, index=True)

    # subscribers | non_subscribers | both
    target = db.Column(db.String(32), nullable=False)

    # queued | running | completed | failed
    status = db.Column(db.String(20), nullable=False, default="queued", index=True)

    # per-segment cap used
    limit_each = db.Column(db.Integer, nullable=False, default=200)

    # counters (overall)
    total_sent = db.Column(db.Integer, nullable=False, default=0)
    total_failed = db.Column(db.Integer, nullable=False, default=0)
    total_targeted = db.Column(db.Integer, nullable=False, default=0)

    # timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)

    # optional debugging info
    last_error = db.Column(db.Text, nullable=True)

    def mark_running(self):
        self.status = "running"
        self.started_at = datetime.utcnow()

    def mark_done(self):
        self.status = "completed"
        self.finished_at = datetime.utcnow()

    def mark_failed(self, err: str):
        self.status = "failed"
        self.last_error = err
        self.finished_at = datetime.utcnow()