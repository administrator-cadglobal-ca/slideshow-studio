"""Public share viewer routes."""
from flask import Blueprint, render_template, request, redirect, url_for, session, abort, jsonify
from app.extensions import db
from app.models.event import ShareToken, Event
from datetime import datetime

bp = Blueprint("share", __name__)


def _load_share(token):
    """Load a valid, non-expired share token or return None."""
    st = db.session.query(ShareToken).filter_by(token=token).first()
    if not st:
        return None
    if st.expires_at and datetime.utcnow() > st.expires_at:
        return None
    return st


def _session_key(token):
    return f"share_auth_{token}"


@bp.route("/s/<token>", methods=["GET", "POST"])
def view_share(token):
    """Public viewer: password gate, then slideshow."""
    st = _load_share(token)
    if not st:
        return render_template("share/invalid.html", is_share_view=True), 404

    session_key = _session_key(token)

    # Handle password submission
    if request.method == "POST":
        submitted = (request.form.get("password") or "").strip()
        expected  = (st.plain_password or "WELCOME").strip()
        if submitted == expected:
            session[session_key] = True
            session.permanent = True
            # Track usage
            st.last_used_at = datetime.utcnow()
            st.use_count = (st.use_count or 0) + 1
            db.session.commit()
            return redirect(url_for("share.view_share", token=token))
        else:
            return render_template("share/password.html", token=token, error="Incorrect password. Try again.", description=st.description, is_share_view=True)

    # If not yet authenticated, show password page
    if not session.get(session_key):
        return render_template("share/password.html", token=token, error=None, description=st.description, is_share_view=True)

    # Authenticated - show slideshow
    from app.services.storage import list_processed_versions_r2, thumb_url
    from app.models.audio import Playlist
    import json

    evt = db.session.get(Event, st.event_id)
    if not evt:
        return render_template("share/invalid.html", is_share_view=True), 404

    # Build versions_data (source + processed)
    versions_data = {}
    photos_ordered = sorted(evt.photos, key=lambda p: p.sort_order)
    if photos_ordered:
        versions_data["source"] = [
            {
                "url":      thumb_url(evt.user_id, evt.id, p.filename),
                "full_url": f"/api/v1/media/photos/{evt.user_id}/{evt.id}/{p.filename}",
                "name":     p.orig_name or p.filename,
            }
            for p in photos_ordered
        ]

    r2_versions = list_processed_versions_r2(evt.user_id, evt.id)
    for ver, frames in sorted(r2_versions.items()):
        versions_data[ver] = [
            {
                "url":      f"/api/v1/media/processed/{evt.user_id}/{evt.id}/{ver}/{f}",
                "full_url": f"/api/v1/media/processed/{evt.user_id}/{evt.id}/{ver}/{f}",
                "name":     f,
            }
            for f in frames
        ]

    # Filter versions if versions_list constraint set
    if st.versions_list:
        try:
            allowed = set(json.loads(st.versions_list))
            versions_data = {k: v for k, v in versions_data.items() if k in allowed}
        except Exception:
            pass

    # Build labels_clips - filter to allowed playlists
    all_playlists_q = db.session.query(Playlist).filter_by(user_id=evt.user_id)
    if st.playlist_ids:
        try:
            allowed_ids = set(int(x) for x in json.loads(st.playlist_ids))
            all_playlists = [p for p in all_playlists_q.all() if p.id in allowed_ids]
        except Exception:
            all_playlists = all_playlists_q.all()
    else:
        all_playlists = all_playlists_q.all()

    labels_clips = {}
    for label in all_playlists:
        clips = []
        for c in label.clips:
            clips.append({
                "id":    c.id,
                "name":  c.name,
                "url":   f"/api/v1/media/audio/{evt.user_id}/original/{c.song.filename}",
                "dur":   c.trim_end or "--:--",
                "start": c.trim_start or "0",
                "end":   c.trim_end,
            })
        labels_clips[str(label.id)] = clips

    # Preferred default version from share
    default_version = st.version or (list(versions_data.keys())[0] if versions_data else "")
    default_playlist_id = evt.playlist_id if evt.playlist_id in [p.id for p in all_playlists] else (all_playlists[0].id if all_playlists else None)

    return render_template("share/viewer.html",
        event=evt,
        token=token,
        share=st,
        versions_data=versions_data,
        all_playlists=all_playlists,
        labels_clips=labels_clips,
        default_version=default_version,
        default_playlist_id=default_playlist_id,
        is_share_view=True,
    )


@bp.route("/s/<token>/logout", methods=["POST"])
def logout_share(token):
    session.pop(_session_key(token), None)
    return redirect(url_for("share.view_share", token=token))