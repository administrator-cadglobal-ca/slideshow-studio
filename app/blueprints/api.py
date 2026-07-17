from flask       import Blueprint, jsonify, Response, stream_with_context, \
                        request, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models  import RenderJob, Event, Photo
import time, json

bp = Blueprint("api", __name__)


# ── Set event label ────────────────────────────────────────────────────────
@bp.route("/events/<event_id>/label", methods=["POST"])
@login_required
def set_event_playlist(event_id):
    from app.models import Event
    from app.models.audio import Playlist
    evt = db.session.query(Event)             .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    playlist_id = request.json.get("playlist_id")
    # Clear any existing event label assignment for this event
    old_label = db.session.query(Playlist)                  .filter_by(event_id=evt.id).first()
    if old_label:
        old_label.event_id = None
    if playlist_id:
        label = db.session.get(Playlist, int(playlist_id))
        if not label or label.user_id != current_user.id:
            return jsonify({"error": "Label not found"}), 404
        label.event_id = evt.id
    db.session.commit()
    return jsonify({"ok": True})


# ── Single label clips ───────────────────────────────────────────────────────
@bp.route("/labels/<int:playlist_id>/clips")
@login_required
def get_label_clips(playlist_id):
    from app.models.audio import Playlist
    label = db.session.get(Playlist, playlist_id)
    if not label or label.user_id != current_user.id:
        return jsonify({"error": "not found"}), 404
    clips = [{
        "id":               c.id,
        "name":             c.display_name,
        "display_name":     c.display_name,
        "url":              f"/api/v1/media/audio/{current_user.id}/original/{c.song.filename}",
        "dur":              c.duration_display,
        "duration_display": c.duration_display,
        "start":            c.start_s,
        "start_s":          c.start_s,
        "end":              c.end_s,
        "end_s":            c.end_s,
    } for c in label.clips]
    return jsonify({"clips": clips, "label": label.name, "count": len(clips)})


# ── Labels API for preview player ────────────────────────────────────────────
@bp.route("/labels")
@login_required
def get_labels():
    from app.models.audio import Playlist
    labels = db.session.query(Playlist)               .filter_by(user_id=current_user.id)               .order_by(Playlist.name).all()
    result = []
    for label in labels:
        result.append({
            "id":    label.id,
            "name":  label.name,
            "color": label.color,
            "clips": [
                {
                    "id":    c.id,
                    "name":  c.display_name,
                    "url":   f"/api/v1/media/audio/{current_user.id}/original/{c.song.filename}",
                    "dur":   c.duration_display,
                    "start": c.start_s,
                    "end":   c.end_s,
                }
                for c in label.clips
            ]
        })
    return jsonify({"labels": result})


# ── Serve source photo ───────────────────────────────────────────────────────
@bp.route("/media/photo/<int:user_id>/<event_id>/source/<filename>")
@login_required
def serve_source_photo(user_id, event_id, filename):
    from flask import send_file
    from app.services.storage import source_dir
    if user_id != current_user.id:
        abort(403)
    path = source_dir(user_id, event_id) / filename
    if not path.exists():
        abort(404)
    return send_file(str(path))


# ── Serve preview photo (1280px) ─────────────────────────────────────────────
@bp.route("/media/photo/<int:user_id>/<event_id>/previews/<filename>")
@login_required
def serve_preview_photo(user_id, event_id, filename):
    from flask import send_file
    from pathlib import Path
    from app.services.storage import event_dir
    if user_id != current_user.id:
        abort(403)
    path = event_dir(user_id, event_id) / "previews" / filename
    if not path.exists():
        # Fall back to source
        from app.services.storage import source_dir
        path = source_dir(user_id, event_id) / filename.replace('prev_', '')
    if not path.exists():
        abort(404)
    return send_file(str(path))


# ── Delete all photos ────────────────────────────────────────────────────────
@bp.route("/events/<event_id>/photos/delete-all", methods=["POST"])
@login_required
def delete_all_photos(event_id):
    from app.services import r2 as R2
    from app.models import Photo
    evt = db.session.get(Event, event_id)
    if not evt or evt.user_id != current_user.id:
        return jsonify({"error": "not found"}), 404
    deleted = 0
    for photo in evt.photos:
        try:
            R2.delete(R2.photo_key(current_user.id, event_id, photo.filename))
            R2.delete(R2.thumb_key(current_user.id, event_id, f"thumb_{photo.filename}"))
            deleted += 1
        except Exception:
            pass
        db.session.delete(photo)
    db.session.commit()
    from app.models import log_activity
    log_activity(evt, "photos_deleted_all", {"count": deleted})
    return jsonify({"ok": True, "deleted": deleted})


# ── Delete single photo ──────────────────────────────────────────────────────
@bp.route("/events/<event_id>/photos/<int:photo_id>/delete", methods=["POST"])
@login_required
def delete_photo(event_id, photo_id):
    from app.services import r2 as R2
    from app.models import Photo
    evt  = db.session.get(Event, event_id)
    photo = db.session.get(Photo, photo_id)
    if not evt or evt.user_id != current_user.id or not photo or photo.event_id != event_id:
        return jsonify({"error": "not found"}), 404
    try:
        R2.delete(R2.photo_key(current_user.id, event_id, photo.filename))
        R2.delete(R2.thumb_key(current_user.id, event_id, f"thumb_{photo.filename}"))
    except Exception:
        pass
    filename_for_log = photo.orig_name or photo.filename
    db.session.delete(photo)
    db.session.commit()
    from app.models import log_activity
    log_activity(evt, "photo_deleted", {"filename": filename_for_log})
    return jsonify({"ok": True})


# ── Photo upload ──────────────────────────────────────────────────────────────
@bp.route("/events/<event_id>/photos/upload", methods=["POST"])
@login_required
def upload_photos(event_id):
    from app.services.storage import save_uploaded_photo_r2 as save_uploaded_photo
    evt = db.session.get(Event, event_id)
    if not evt or evt.user_id != current_user.id:
        return jsonify({"error": "not found"}), 404

    files    = request.files.getlist("photos")
    uploaded = 0
    errors   = []

    # Get existing filenames in this event to detect duplicates
    existing_names = {p.orig_name for p in evt.photos}

    for f in files:
        if not f or not f.filename:
            continue
        print(f"[UPLOAD] Processing: {f.filename}")
        # Skip duplicate — same original filename already in event
        if f.filename in existing_names:
            print(f"[UPLOAD] Skipping duplicate: {f.filename}")
            continue
        try:
            print(f"[UPLOAD] Uploading to R2: {f.filename}")
            result = save_uploaded_photo(f, current_user.id, event_id)
            print(f"[UPLOAD] R2 success: {result.get('filename')}")
            from app.models import Photo
            photo = Photo(
                event_id   = event_id,
                filename     = result["filename"],
                orig_name    = result["orig_name"],
                file_size    = result["file_size"],
                width        = result.get("width"),
                height       = result.get("height"),
                orientation  = result.get("orientation", "landscape"),
                sort_order   = len(evt.photos) + uploaded,
                exif_date    = result.get("exif_date"),
                exif_date_str= result.get("exif_date_str"),
                camera_make  = result.get("camera_make"),
                camera_model = result.get("camera_model"),
                lens_model   = result.get("lens_model"),
                focal_length = result.get("focal_length"),
                aperture     = result.get("aperture"),
                shutter_speed= result.get("shutter_speed"),
                iso          = result.get("iso"),
                gps_lat      = result.get("gps_lat"),
                gps_lon      = result.get("gps_lon"),
                gps_alt      = result.get("gps_alt"),
                gps_location = result.get("gps_location"),
                gps_place    = result.get("gps_place"),
                gps_country  = result.get("gps_country"),
            )
            db.session.add(photo)
            uploaded += 1
        except Exception as e:
            errors.append(f"{f.filename}: {str(e)}")
            print(f"[UPLOAD] Error: {f.filename}: {e}")

    db.session.commit()
    skipped = len(files) - uploaded - len(errors)
    if uploaded > 0:
        from app.models import log_activity
        log_activity(evt, "photos_uploaded", {"count": uploaded, "skipped": skipped, "errors": errors})
    return jsonify({
        "uploaded": uploaded,
        "skipped":  max(0, skipped),
        "errors":   errors,
        "total":    len(evt.photos),
    })

@bp.route("/renders/<job_id>/progress")
@login_required
def render_progress(job_id: str):
    def event_stream():
        last_len = 0
        for _ in range(600):
            job = db.session.get(RenderJob, job_id)
            if not job or job.event.user_id != current_user.id:
                yield f"event: error\ndata: {json.dumps({'error':'not found'})}\n\n"
                return
            new_log = (job.log_text or "")[last_len:]
            last_len += len(new_log)
            data = {"status": job.status, "progress_pct": round(job.progress_pct or 0, 1),
                    "current_version": job.current_version or "",
                    "current_step": job.current_step or "", "log": new_log,
                    "output_count": job.output_count}
            yield f"event: progress\ndata: {json.dumps(data)}\n\n"
            if job.status in ("complete", "failed", "cancelled"):
                yield f"event: done\ndata: {json.dumps({'status': job.status})}\n\n"
                return
            db.session.expire_all()
            time.sleep(1)
    return Response(stream_with_context(event_stream()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@bp.route("/events/<event_id>/render", methods=["POST"])
@login_required
def start_render(event_id: str):
    event = db.session.query(Event).filter_by(id=event_id, user_id=current_user.id).first_or_404()
    mode = request.json.get("mode", "production")
    job  = RenderJob(event_id=event.id, mode=mode)
    if mode == "dev":
        job.dev_images          = request.json.get("dev_images", 20)
        job.dev_songs           = request.json.get("dev_songs", 4)
        job.dev_images_per_song = request.json.get("dev_images_per_song", 5)
    db.session.add(job)
    event.status = "rendering"
    db.session.commit()
    from app.services.render_task import run_render
    task = run_render.delay(job.id)
    job.celery_task_id = task.id
    db.session.commit()
    return jsonify({"job_id": job.id, "status": "queued"})

@bp.route("/renders/<job_id>/cancel", methods=["POST"])
@login_required
def cancel_render(job_id: str):
    job = db.session.get(RenderJob, job_id)
    if not job or job.event.user_id != current_user.id:
        abort(404)
    if job.celery_task_id:
        from app.extensions import celery_app
        celery_app.control.revoke(job.celery_task_id, terminate=True)
    job.status = "cancelled"
    db.session.commit()
    return jsonify({"status": "cancelled"})

@bp.route("/events/<event_id>/photos/reorder", methods=["POST"])
@login_required
def reorder_photos(event_id: str):
    event = db.session.query(Event).filter_by(id=event_id, user_id=current_user.id).first_or_404()
    for i, photo_id in enumerate(request.json.get("order", [])):
        photo = db.session.get(Photo, photo_id)
        if photo and photo.event_id == event.id:
            photo.sort_order = i
    db.session.commit()
    return jsonify({"ok": True})

@bp.route("/storage")
@login_required
def storage():
    return jsonify({"used": current_user.storage_used, "quota": current_user.quota_bytes,
                    "pct": round(current_user.storage_pct, 1)})


# ── Media serving ─────────────────────────────────────────────────────────────
from flask import send_file as _sf, abort as _abort
from app.services.storage import (thumb_dir as _td, output_dir as _od,
                                   processed_dir as _pd, audio_dir as _aud)

@bp.route("/media/thumbs/<int:uid>/<pid>/<filename>",
          endpoint="serve_thumb")
@login_required
def serve_thumb(uid, pid, filename):
    from flask import redirect
    from app.services import r2 as R2
    if uid != current_user.id and not current_user.is_admin:
        _abort(403)
    key = R2.thumb_key(uid, pid, filename)
    print(f"[THUMB] key={key}")
    try:
        url = R2.presigned_url(key, 3600)
        print(f"[THUMB] redirecting to R2 URL")
        return redirect(url)
    except Exception as e:
        print(f"[THUMB] presigned error: {e}")
        try:
            orig = filename.replace("thumb_", "")
            url2 = R2.presigned_url(R2.photo_key(uid, pid, orig), 3600)
            return redirect(url2)
        except Exception as e2:
            print(f"[THUMB] fallback error: {e2}")
            _abort(404)

@bp.route("/media/photos/<int:uid>/<pid>/<filename>",
          endpoint="serve_photo")
@login_required
def serve_photo(uid, pid, filename):
    from flask import redirect
    from app.services import r2 as R2
    if uid != current_user.id and not current_user.is_admin:
        _abort(403)
    key = R2.photo_key(uid, pid, filename)
    return redirect(R2.presigned_url(key, 3600))


@bp.route("/media/output/<int:uid>/<pid>/<filename>",
          endpoint="serve_output")
@login_required
def serve_output(uid, pid, filename):
    if uid != current_user.id and not current_user.is_admin:
        _abort(403)
    f = _od(uid, pid) / filename
    if not f.exists(): _abort(404)
    return _sf(str(f), as_attachment=True)

@bp.route("/media/processed/<int:uid>/<pid>/<ver>/<filename>",
          endpoint="serve_processed")
@login_required
def serve_processed(uid, pid, ver, filename):
    from flask import redirect
    from app.services import r2 as R2
    if uid != current_user.id and not current_user.is_admin:
        _abort(403)
    # Try thumbnail first, fall back to full frame
    if filename.startswith("thumb_"):
        key = R2.processed_thumb_key(uid, pid, ver, filename)
    else:
        key = R2.processed_key(uid, pid, ver, filename)
    return redirect(R2.presigned_url(key, 3600))

@bp.route("/media/audio/<int:uid>/<sub>/<filename>",
          endpoint="serve_audio")
@login_required
def serve_audio(uid, sub, filename):
    from flask import redirect
    from app.services import r2 as R2
    if uid != current_user.id and not current_user.is_admin:
        _abort(403)
    key = R2.audio_key(uid, filename)
    print(f"[AUDIO] serving key={key}")
    try:
        url = R2.presigned_url(key, 3600)
        return redirect(url)
    except Exception as e:
        print(f"[AUDIO] error: {e}")
        _abort(404)


# ── Photo note ────────────────────────────────────────────────────────────────
@bp.route("/v1/events/<event_id>/photos/<int:photo_id>/note", methods=["POST"])
@login_required
def save_photo_note(event_id, photo_id):
    from app.models import Event, Photo
    evt  = db.session.get(Event, event_id)
    if not evt or evt.user_id != current_user.id:
        return jsonify({"error": "not found"}), 404
    photo = db.session.get(Photo, photo_id)
    if not photo or photo.event_id != event_id:
        return jsonify({"error": "not found"}), 404
    note  = (request.json.get("note") or "").strip()[:200]
    photo.note = note or None
    db.session.commit()
    return jsonify({"ok": True, "note": photo.note})


# ── Caption style ─────────────────────────────────────────────────────────────
@bp.route("/v1/events/<event_id>/caption-style", methods=["POST"])
@login_required
def save_caption_style(event_id):
    from app.models import Event
    import json
    evt = db.session.get(Event, event_id)
    if not evt or evt.user_id != current_user.id:
        return jsonify({"error": "not found"}), 404
    style = {
        "position":      request.json.get("position",      "bottom"),
        "size":          request.json.get("size",          "medium"),
        "color":         request.json.get("color",         "#ffffff"),
        "background":    request.json.get("background",    "gradient"),
        "burn_captions": request.json.get("burn_captions", True),
    }
    evt.caption_style = json.dumps(style)
    db.session.commit()
    return jsonify({"ok": True})


# ── Photo metadata ────────────────────────────────────────────────────────────
@bp.route("/v1/events/<event_id>/photos/<int:photo_id>/meta")
@login_required
def photo_meta(event_id, photo_id):
    from app.models import Event, Photo
    evt  = db.session.get(Event, event_id)
    if not evt or evt.user_id != current_user.id:
        return jsonify({"error": "not found"}), 404
    photo = db.session.get(Photo, photo_id)
    if not photo or photo.event_id != event_id:
        return jsonify({"error": "not found"}), 404
    return jsonify(photo.to_meta_dict())


# ── Re-extract EXIF for an existing photo ─────────────────────────────────────
@bp.route("/v1/events/<event_id>/photos/<int:photo_id>/reextract", methods=["POST"])
@login_required
def reextract_exif(event_id, photo_id):
    from app.models import Event, Photo
    from app.services.storage import source_dir
    from app.services.exif import extract_metadata, reverse_geocode
    evt  = db.session.get(Event, event_id)
    if not evt or evt.user_id != current_user.id:
        return jsonify({"error": "not found"}), 404
    photo = db.session.get(Photo, photo_id)
    if not photo or photo.event_id != event_id:
        return jsonify({"error": "not found"}), 404

    src = source_dir(current_user.id, event_id) / photo.filename
    if not src.exists():
        return jsonify({"error": "source file not found"}), 404

    meta = extract_metadata(src)
    if meta.get("gps_lat") and meta.get("gps_lon"):
        geo = reverse_geocode(meta["gps_lat"], meta["gps_lon"])
        meta.update(geo)

    for field, val in meta.items():
        if hasattr(photo, field):
            setattr(photo, field, val)
    db.session.commit()
    return jsonify(photo.to_meta_dict())
