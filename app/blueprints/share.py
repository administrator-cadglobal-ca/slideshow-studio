"""Public share routes — no login required."""
from flask import Blueprint, render_template, abort, request, jsonify
from app.extensions import db
from app.models.project import Project, ShareToken
from app.models.audio import AudioLabel
from app.services.storage import processed_dir, thumb_url, processed_url, audio_dir
import json
from datetime import datetime

bp = Blueprint("share", __name__)


@bp.route("/s/<token>")
def public_player(token):
    """Public slideshow player — no login required."""
    st = db.session.query(ShareToken).filter_by(token=token, share_type="public").first_or_404()
    if st.is_expired:
        abort(410)  # Gone

    proj = db.session.get(Project, st.project_id)
    if not proj:
        abort(404)

    # Update usage stats
    st.last_used_at = datetime.utcnow()
    st.use_count += 1
    db.session.commit()

    # Get processed versions
    proc_base = processed_dir(st.created_by, proj.id)
    processed_versions = []
    processed_images = {}
    if proc_base.exists():
        for ver_dir in sorted(proc_base.iterdir()):
            if ver_dir.is_dir() and ver_dir.name != "thumbs":
                imgs = sorted([f.name for f in ver_dir.glob("*.jpg")
                               if f.parent == ver_dir])
                if imgs:
                    processed_versions.append(ver_dir.name)
                    processed_images[ver_dir.name] = imgs

    # Default version
    default_version = st.version or (processed_versions[0] if processed_versions else "source")

    # Get allowed labels
    allowed_label_ids = json.loads(st.label_ids) if st.label_ids else None
    labels_query = db.session.query(AudioLabel)\
                     .filter_by(user_id=st.created_by)\
                     .order_by(AudioLabel.name)
    if allowed_label_ids:
        labels_query = labels_query.filter(AudioLabel.id.in_(allowed_label_ids))
    all_labels = labels_query.all()

    # Default label = project's assigned label
    project_label = proj.audio_label

    # Build source images (fallback if no processed)
    photos_ordered = sorted(proj.photos, key=lambda p: p.sort_order)

    return render_template("share/player.html",
        token=st, project=proj,
        processed_versions=processed_versions,
        processed_images=processed_images,
        default_version=default_version,
        all_labels=all_labels,
        project_label=project_label,
        photos=photos_ordered,
        user_id=st.created_by,
        thumb_url=thumb_url,
        processed_url=processed_url,
    )


@bp.route("/s/<token>/clips/<int:label_id>")
def public_label_clips(token, label_id):
    """Return clips for a label — public, token-gated."""
    st = db.session.query(ShareToken).filter_by(token=token, share_type="public").first()
    if not st or st.is_expired:
        abort(403)
    # Verify label belongs to project owner
    label = db.session.get(AudioLabel, label_id)
    if not label or label.user_id != st.created_by:
        abort(403)
    # Verify label is allowed
    if st.label_ids:
        allowed = json.loads(st.label_ids)
        if label_id not in allowed:
            abort(403)
    clips = []
    for c in label.clips:
        src = audio_dir(st.created_by, "original") / c.song.filename
        clips.append({
            "id": c.id, "name": c.display_name,
            "dur": c.duration_display,
            "url": f"/s/{token}/audio/{c.song.filename}",
            "start": c.start_s or 0, "end": c.end_s,
        })
    return jsonify({"clips": clips, "label": label.name})


@bp.route("/s/<token>/audio/<filename>")
def public_audio(token, filename):
    """Serve audio file — public, token-gated."""
    from flask import send_file
    st = db.session.query(ShareToken).filter_by(token=token, share_type="public").first()
    if not st or st.is_expired:
        abort(403)
    path = audio_dir(st.created_by, "original") / filename
    if not path.exists():
        abort(404)
    return send_file(str(path))


@bp.route("/s/<token>/media/<version>/<filename>")
def public_media(token, version, filename):
    """Serve processed frame or thumbnail — public, token-gated."""
    from flask import send_file
    st = db.session.query(ShareToken).filter_by(token=token, share_type="public").first()
    if not st or st.is_expired:
        abort(403)
    # Try thumb first, fall back to full
    proc = processed_dir(st.created_by, st.project_id, version)
    path = proc / "thumbs" / filename
    if not path.exists():
        path = proc / filename
    if not path.exists():
        abort(404)
    return send_file(str(path))


@bp.route("/s/<token>/source/<filename>")
def public_source(token, filename):
    """Serve source photo thumbnail — public, token-gated."""
    from flask import send_file
    from app.services.storage import source_dir
    st = db.session.query(ShareToken).filter_by(token=token, share_type="public").first()
    if not st or st.is_expired:
        abort(403)
    path = source_dir(st.created_by, st.project_id).parent / "thumbs" / filename
    if not path.exists():
        path = source_dir(st.created_by, st.project_id) / filename
    if not path.exists():
        abort(404)
    return send_file(str(path))
