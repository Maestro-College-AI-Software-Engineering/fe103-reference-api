from datetime import datetime, timezone

from .extensions import db


def utcnow():
    """The current time in UTC, stored without a timezone (same on SQLite and Postgres)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_utc(value):
    """2026-09-29 22:15:03 -> "2026-09-29T22:15:03Z"."""
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(60))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    tasks = db.relationship("Task", back_populates="owner", cascade="all, delete-orphan")

    def to_dict(self):
        return {"id": self.id, "username": self.username, "display_name": self.display_name}


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(1000))
    done = db.Column(db.Boolean, nullable=False, default=False)
    due_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    owner = db.relationship("User", back_populates="tasks")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "done": self.done,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": iso_utc(self.created_at),
            "owner_id": self.owner_id,
        }
