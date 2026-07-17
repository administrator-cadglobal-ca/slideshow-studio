"""Authorization helpers shared between share and API blueprints."""
from functools import wraps
from datetime import datetime
from flask import abort, session
from flask_login import current_user
from app.extensions import db
from app.models.event import ShareToken


def event_share_authorized(event_user_id, event_id):
    """True if current request may view media for this event."""
    try:
        if current_user.is_authenticated:
            if current_user.id == event_user_id:
                return True
            if getattr(current_user, "is_admin", False):
                return True
    except Exception:
        pass
    for key in list(session.keys()):
        if not key.startswith("share_auth_"):
            continue
        token = key[len("share_auth_"):]
        st = db.session.query(ShareToken).filter_by(token=token).first()
        if st and str(st.event_id) == str(event_id):
            if st.expires_at and datetime.utcnow() > st.expires_at:
                continue
            return True
    return False


def share_or_login_required(f):
    """Decorator - allow logged-in owner OR share-session viewer."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        uid = kwargs.get("uid") or kwargs.get("user_id")
        pid = kwargs.get("pid") or kwargs.get("event_id")
        if uid is None or pid is None:
            abort(400)
        if not event_share_authorized(int(uid), str(pid)):
            abort(403)
        return f(*args, **kwargs)
    return wrapped