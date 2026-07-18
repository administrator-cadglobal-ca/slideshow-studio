"""Render share blueprint - password-gated public MP4 playback."""
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.models import Event
from app.models.event import RenderShare
from datetime import datetime, timedelta
import secrets

bp = Blueprint("render_share", __name__)


# ── OWNER ENDPOINTS (manage shares under /events/<event_id>/) ────────────────

def _register_owner_routes(events_bp):
    """Attach owner-side endpoints to the events blueprint at import time."""
    pass  # We add them in events.py directly


# ── PUBLIC VIEWER ENDPOINTS (under /r/) ──────────────────────────────────────

@bp.route("/r/<token>", methods=["GET", "POST"])
def view_render(token):
    """Public: password gate, then video player."""
    rs = db.session.query(RenderShare).filter_by(token=token).first()
    if not rs:
        return render_template("share/invalid.html", is_share_view=True), 404
    if rs.is_expired:
        return render_template("share/invalid.html", is_share_view=True), 410

    session_key = f"rshare_{token}"

    if request.method == "POST":
        submitted = (request.form.get("password") or "").strip()
        expected = (rs.plain_password or "WELCOME").strip()
        if submitted.lower() == expected.lower():
            session[session_key] = True
            session.permanent = True
            rs.last_used_at = datetime.utcnow()
            rs.use_count = (rs.use_count or 0) + 1
            db.session.commit()
            return redirect(url_for("render_share.view_render", token=token))
        else:
            return render_template("share/render_password.html",
                token=token, error="Incorrect password. Try again.",
                is_share_view=True), 401

    if not session.get(session_key):
        return render_template("share/render_password.html",
            token=token, error=None, is_share_view=True)

    # Authenticated - show player
    evt = db.session.get(Event, rs.event_id)
    return render_template("share/render_player.html",
        token=token,
        filename=rs.filename,
        event_name=evt.name if evt else "",
        is_share_view=True,
    )


@bp.route("/r/<token>/video")
def view_render_video(token):
    """Session-authenticated redirect to R2 presigned URL for inline playback."""
    rs = db.session.query(RenderShare).filter_by(token=token).first()
    if not rs or rs.is_expired:
        abort(404)
    session_key = f"rshare_{token}"
    if not session.get(session_key):
        abort(403)
    from app.services import r2 as R2
    evt = db.session.get(Event, rs.event_id)
    if not evt:
        abort(404)
    key = R2.output_key(evt.user_id, rs.event_id, rs.filename)
    url = R2.presigned_url(key, expires=3600)
    return redirect(url)


@bp.route("/r/<token>/logout", methods=["POST"])
def logout_render(token):
    session.pop(f"rshare_{token}", None)
    return redirect(url_for("render_share.view_render", token=token))