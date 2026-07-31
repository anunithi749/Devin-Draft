"""Database models."""

from __future__ import annotations

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Submission(db.Model):
    """One logged entry. Points are computed and stored on approval so the
    leaderboard reads a stable number, but the scoring rules remain the single
    source of truth in scoring.py."""

    __tablename__ = "submissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    team = db.Column(db.String(120), nullable=False, default="")
    track = db.Column(db.String(40), nullable=False)
    activity_type = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    evidence_url = db.Column(db.String(500), default="")
    impact_measured = db.Column(db.Boolean, default=False)
    highly_scalable = db.Column(db.Boolean, default=False)
    points = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "team": self.team,
            "track": self.track,
            "activity_type": self.activity_type,
            "title": self.title,
            "description": self.description,
            "evidence_url": self.evidence_url,
            "impact_measured": self.impact_measured,
            "highly_scalable": self.highly_scalable,
            "points": self.points,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Season(db.Model):
    """Program configuration. A single active row drives the scarcity UI."""

    __tablename__ = "seasons"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default="Season 1")
    seats_total = db.Column(db.Integer, nullable=False, default=5)
    seats_filled = db.Column(db.Integer, nullable=False, default=0)
    closes_on = db.Column(db.Date, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "seats_total": self.seats_total,
            "seats_filled": self.seats_filled,
            "seats_remaining": max(0, self.seats_total - self.seats_filled),
            "closes_on": self.closes_on.isoformat() if self.closes_on else None,
        }
