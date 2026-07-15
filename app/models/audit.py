"""Admin audit log — every state-changing admin action is recorded here."""
import json
from datetime import datetime, timezone
from flask import request
from flask_login import current_user
from app.extensions import db


class AdminAuditLog(db.Model):
    __tablename__ = "admin_audit_log"

    id              = db.Column(db.Integer, primary_key=True)
    admin_user_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_user_id  = db.Column(db.Integer, db.ForeignKey("users.id"))
    target_type     = db.Column(db.String(50), nullable=False)
    action          = db.Column(db.String(50), nullable=False)
    payload_json    = db.Column(db.Text)
    ip              = db.Column(db.String(45))
    user_agent      = db.Column(db.String(500))
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def payload(self):
        try:
            return json.loads(self.payload_json) if self.payload_json else {}
        except Exception:
            return {}


def log_admin_action(action, target_user_id=None, target_type="user", payload=None):
    """
    Record an admin action. Call this INSIDE the request handler.
    Does not commit - the surrounding db.session.commit() picks it up.
    """
    entry = AdminAuditLog(
        admin_user_id  = current_user.id,
        target_user_id = target_user_id,
        target_type    = target_type,
        action         = action,
        payload_json   = json.dumps(payload) if payload else None,
        ip             = (request.headers.get("CF-Connecting-IP")
                          or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                          or request.remote_addr),
        user_agent     = (request.user_agent.string or "")[:500],
    )
    db.session.add(entry)
    return entry