from datetime import datetime, timezone
import json
from app.extensions import db


class EventActivity(db.Model):
    """Audit log of actions performed on an event."""
    __tablename__ = "event_activities"

    id         = db.Column(db.Integer, primary_key=True)
    event_id   = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False, index=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action     = db.Column(db.String(50), nullable=False)
    details    = db.Column(db.Text)  # JSON blob
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    event = db.relationship("Event")
    user  = db.relationship("User")

    def details_dict(self):
        if not self.details:
            return {}
        try:
            return json.loads(self.details)
        except Exception:
            return {}

    def to_dict(self):
        return {
            "id":         self.id,
            "event_id":   self.event_id,
            "user_id":    self.user_id,
            "action":     self.action,
            "details":    self.details_dict(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "user_name":  (self.user.first_name + " " + self.user.last_name).strip() if self.user else "",
        }


def log_activity(event, action, details=None, user=None):
    """Convenience helper: log an event activity and commit.

    event   - Event instance or event_id string
    action  - short action name (upload, photo_delete, process_start, etc.)
    details - dict, will be JSON-encoded
    user    - User instance or user_id; if None, tries current_user from Flask-Login
    """
    from flask_login import current_user
    if user is None:
        user = current_user
    # Force resolution of the LocalProxy and grab the id
    if hasattr(user, "_get_current_object"):
        user = user._get_current_object()
    try:
        user_id = user.id
    except AttributeError:
        user_id = int(user)
    event_id = event.id if hasattr(event, "id") else str(event)
    activity = EventActivity(
        event_id=event_id,
        user_id=user_id,
        action=action,
        details=json.dumps(details) if details else None,
    )
    db.session.add(activity)
    db.session.commit()
    return activity