from pathlib import Path
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, send_file, jsonify, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Event, Photo
from app.services.storage import event_dir, source_dir, processed_dir, output_dir, thumb_url, processed_url, output_url, save_uploaded_photo
import uuid

bp = Blueprint("events", __name__)


def _slugify(text: str) -> str:
    """Simple slug generator — no external dependency needed."""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text[:80]

LOOP_COLORS = ["#1e3a52","#2a1e3a","#0f3a2a","#3a1e1e","#1e2e3a","#2a3a1e"]
RENDER_VERSIONS = {
    "hd":          {"label":"HD 1080p",      "res":(1920,1080)},
    "4k":          {"label":"4K 2160p",      "res":(3840,2160)},
    "2k":          {"label":"2K 1440p",      "res":(2560,1440)},
    "sd":          {"label":"SD 720p",       "res":(1280,720)},
    "phone_smart": {"label":"Phone Smart",   "res":(1080,1920)},
    "phone_stack": {"label":"Phone Stack",   "res":(1080,1920)},
    "phone_split": {"label":"Phone Split",   "res":(1080,1920)},
    "phone_bars":  {"label":"Phone Bars",    "res":(1080,1920)},
    "phone_only":  {"label":"Phone Only",    "res":(1080,1920)},
}

@bp.route("/")
@login_required
def index():
    from app.models.audio import Playlist
    events = db.session.query(Event)\
                 .filter_by(user_id=current_user.id)\
                 .order_by(Event.updated_at.desc()).all()
    playlists = db.session.query(Playlist)\
                    .filter_by(user_id=current_user.id)\
                    .order_by(Playlist.sort_order, Playlist.name).all()
    # Resolve selected event from ?event= or default to first
    requested_id = request.args.get("event", "").strip()
    selected_event = None
    if requested_id:
        selected_event = next((e for e in events if e.id == requested_id), None)
    if not selected_event and events:
        selected_event = events[0]
    return render_template("events/index.html", events=events,
                           playlists=playlists,
                           selected_event=selected_event,
                           thumb_url=thumb_url,
                           loop_colors=LOOP_COLORS)

@bp.route("/new", methods=["GET","POST"])
@login_required
def new():
    if request.method == "POST":
        name    = request.form.get("name","").strip()
        if not name:
            flash("Event name is required.","error")
            return render_template("events/new.html", render_versions=RENDER_VERSIONS)
        versions = ",".join(request.form.getlist("render_versions")) or "hd,4k,phone_smart,phone_stack"
        evt = Event(
            id=str(uuid.uuid4()), user_id=current_user.id,
            name=name, slug=_slugify(name),
            title_text=request.form.get("title_text","").strip() or name,
            end_text=request.form.get("end_text","Thank You for Watching").strip(),
            render_versions=versions,
            title_bg=current_user.pref_title_bg,
            title_color=current_user.pref_title_color,
            transition=current_user.pref_transition,
            fps=current_user.pref_fps,
        )
        db.session.add(evt)
        db.session.commit()
        from app.models import log_activity
        log_activity(evt, "event_created", {"name": name})
        flash(f"Event '{name}' created.", "success")
        return redirect(url_for("events.show", event_id=evt.id))
    return render_template("events/new.html", render_versions=RENDER_VERSIONS)

@bp.route("/<event_id>")
@login_required
def show(event_id):
    # Backward-compatible redirect: /<event_id> -> /?event=<event_id>
    return redirect(url_for("events.index", event=event_id))

@bp.route("/<event_id>/settings", methods=["GET","POST"])
@login_required
def settings(event_id):
    evt = db.session.query(Event)\
             .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    return render_template("events/settings.html", event=evt, render_versions=RENDER_VERSIONS)

@bp.route("/<event_id>/settings/save", methods=["POST"])
@login_required
def save_settings(event_id):
    evt = db.session.query(Event)\
             .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    evt.name                  = request.form.get("name", evt.name).strip()
    evt.slug                  = request.form.get("slug", evt.slug).strip()
    evt.title_text            = request.form.get("title_text","")
    evt.title_subtitle        = request.form.get("title_subtitle","")
    evt.title_duration        = float(request.form.get("title_duration",5))
    evt.title_bg              = request.form.get("title_bg","#0d1b2a")
    evt.end_text              = request.form.get("end_text","")
    evt.end_duration          = float(request.form.get("end_duration",4))
    evt.image_duration        = float(request.form.get("image_duration",3))
    evt.fps                   = int(request.form.get("fps",24))
    evt.transition            = request.form.get("transition","fade")
    evt.fade_duration         = float(request.form.get("fade_duration",1))
    evt.image_order           = request.form.get("image_order","sequential")
    evt.auto_timing           = "auto_timing"         in request.form
    evt.complete_last_song    = "complete_last_song"  in request.form
    evt.stitch_portraits      = "stitch_portraits"    in request.form
    evt.save_processed_images = "save_processed_images" in request.form
    evt.save_images_confirm   = "save_images_confirm" in request.form
    versions = request.form.getlist("render_versions")
    evt.render_versions       = ",".join(versions) if versions else "hd"
    db.session.commit()
    from app.models import log_activity
    log_activity(evt, "settings_saved", {"render_versions": evt.render_versions})
    flash("Settings saved.", "success")
    return redirect(url_for("events.show", event_id=evt.id))

@bp.route("/<event_id>/set-playlist", methods=["POST"])
@login_required
def set_playlist(event_id):
    evt = db.session.query(Event)\
             .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    from app.models import log_activity, Playlist
    pid_raw = request.form.get("playlist_id", "").strip()
    new_pid = int(pid_raw) if pid_raw else None
    old_pid = evt.playlist_id
    evt.playlist_id = new_pid
    db.session.commit()
    if old_pid != new_pid:
        pl_name = ""
        if new_pid:
            pl = db.session.get(Playlist, new_pid)
            pl_name = pl.name if pl else ""
        log_activity(evt, "playlist_assigned", {"playlist_id": new_pid, "playlist_name": pl_name})
    return jsonify({"ok": True, "playlist_id": evt.playlist_id})

@bp.route("/<event_id>/activities")
@login_required
def get_activities(event_id):
    from app.models import EventActivity
    evt = db.session.query(Event)\
             .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    limit = int(request.args.get("limit", 100))
    activities = db.session.query(EventActivity)\
                    .filter_by(event_id=evt.id)\
                    .order_by(EventActivity.created_at.desc())\
                    .limit(limit).all()
    return jsonify({"activities": [a.to_dict() for a in activities]})

@bp.route("/<event_id>/delete", methods=["GET","POST"])
@login_required
def delete(event_id):
    evt = db.session.query(Event)\
             .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    from app.services.storage import delete_event_files
    delete_event_files(current_user.id, event_id)
    db.session.delete(evt)
    db.session.commit()
    flash(f"Event '{evt.name}' deleted.", "success")
    return redirect(url_for("events.index"))

@bp.route("/<event_id>/preview")
@login_required
def preview(event_id):
    from flask import current_app
    evt = db.session.query(Event)\
             .filter_by(id=event_id, user_id=current_user.id).first_or_404()

    # Build processed versions dict: {version_name: [{url, name}]}
    proc_base = processed_dir(current_user.id, event_id)
    versions_data = {}
    processed_versions = []
    photos_ordered = sorted(evt.photos, key=lambda p: p.sort_order)
    photo_captions = [p.caption or "" for p in photos_ordered]
    l2_mode = evt.caption_line2 or "date_location"

    # Always add "source" version using original uploaded photos
    if photos_ordered:
        processed_versions.append("source")
        versions_data["source"] = [
            {
                "url":      thumb_url(current_user.id, event_id, p.filename),
                "full_url": f"/api/v1/media/photos/{current_user.id}/{event_id}/{p.filename}",
                "name":     p.orig_name,
                "note":     p.note or "",
                "line2":    p.auto_line2(l2_mode),
                "date":     p.exif_date.strftime("%b %d, %Y") if p.exif_date else "",
                "caption":  p.caption or "",
            }
            for p in photos_ordered
        ]

    # Get audio labels for preview player
    from app.models.audio import Playlist
    all_labels = db.session.query(Playlist)                   .filter_by(user_id=current_user.id)                   .order_by(Playlist.name).all()

    # Build songs_data — flat list for the default label (or first label)
    default_label = evt.playlist or (all_labels[0] if all_labels else None)
    songs_data = []
    if default_label:
        songs_data = [
            {
                "id":    c.id,
                "name":  c.name,
                "url":   f"/api/v1/media/audio/{current_user.id}/original/{c.song.filename}",
                "dur":   c.trim_end or "--:--",
                "start": c.trim_start or "0",
                "end":   c.trim_end,
            }
            for c in default_label.clips
        ]

    # Build labels_clips and audio_files for preview player
    labels_clips = {}
    audio_files  = []
    seen_songs   = set()
    for label in all_labels:
        clips = []
        for c in label.clips:
            clips.append({
                "id":    c.id,
                "name":  c.name,
                "url":   f"/api/v1/media/audio/{current_user.id}/original/{c.song.filename}",
                "dur":   c.trim_end or "--:--",
                "start": c.trim_start or "0",
                "end":   c.trim_end,
            })
            if c.song.id not in seen_songs:
                seen_songs.add(c.song.id)
                audio_files.append(c.song)  # Pass song objects for template
        labels_clips[str(label.id)] = clips

    # Load processed versions from R2
    from app.services.storage import list_processed_versions_r2
    r2_versions = list_processed_versions_r2(current_user.id, event_id)
    for ver, frames in sorted(r2_versions.items()):
        processed_versions.append(ver)
        versions_data[ver] = [
            {
                "url":      f"/api/v1/media/processed/{current_user.id}/{event_id}/{ver}/{f}",
                "full_url": f"/api/v1/media/processed/{current_user.id}/{event_id}/{ver}/{f}",
                "name":     f,
                "note":     "",
                "line2":    "",
                "date":     "",
                "caption":  photo_captions[i] if i < len(photo_captions) else "",
            }
            for i, f in enumerate(frames)
        ]

    all_events = db.session.query(Event)\
                    .filter_by(user_id=current_user.id)\
                    .order_by(Event.updated_at.desc()).all()
    return render_template("events/preview.html",
        event=evt,
        all_events=all_events,
        processed_versions=processed_versions,
        versions_data=versions_data,
        songs_data=songs_data,
        all_labels=all_labels,
        labels_clips=labels_clips,
        event_playlist_id=evt.playlist.id if evt.playlist else None,
        audio_files=audio_files,
    )


@bp.route("/<event_id>/notes")
@login_required
def notes(event_id):
    from app.services.storage import thumb_url as _thumb_url
    evt = db.session.query(Event)\
             .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    return render_template("events/notes.html",
        event=evt,
        photos=evt.photos,
        thumb_url=_thumb_url,
    )

@bp.route("/<event_id>/process", methods=["POST"])
@login_required
def process_photos(event_id):
    """Process source photos into HD/SD frames using Pillow."""
    from app.services.storage import source_dir, processed_dir
    from PIL import Image, ImageFilter
    import threading

    evt = db.session.query(Event)             .filter_by(id=event_id, user_id=current_user.id).first_or_404()

    resolutions    = request.json.get("resolutions", ["hd"])
    allow_upscale  = request.json.get("allow_upscale", False)
    enhance        = request.json.get("enhance", False)
    from app.models import log_activity
    log_activity(evt, "process_started", {"resolutions": resolutions, "allow_upscale": allow_upscale, "photo_count": len(evt.photos)})

    SIZES = {
        "sd": [(1280, 720),  (720,  1280)],
        "hd": [(1920, 1080), (1080, 1920)],
        "2k": [(2560, 1440), (1440, 2560)],
        "4k": [(3840, 2160), (2160, 3840)],
    }
    PREFIX = {
        "sd-landscape": "SDL", "sd-portrait": "SDP",
        "hd-landscape": "HDL", "hd-portrait": "HDP",
        "2k-landscape": "2KL", "2k-portrait": "2KP",
        "4k-landscape": "4KL", "4k-portrait": "4KP",
    }

    jobs = []
    for res in resolutions:
        if res not in SIZES:
            continue
        (lW, lH), (pW, pH) = SIZES[res]
        jobs.append((f"{res}-landscape", lW, lH))
        jobs.append((f"{res}-portrait",  pW, pH))

    if not jobs:
        return jsonify({"error": "No valid resolutions"}), 400

    photos = sorted(evt.photos, key=lambda p: p.sort_order)
    if not photos:
        return jsonify({"error": "No photos"}), 400

    # Photos are now in R2 — just pass filenames, run() downloads them
    items_data = [(p.filename, None) for p in photos]

    # all_jobs: version, dummy_dst (not used, R2), W, H, prefix
    import tempfile as _tmpmod
    from pathlib import Path as _Path
    _dummy_base = _Path(_tmpmod.mkdtemp())
    all_jobs = [(v, _dummy_base / v, W, H, PREFIX.get(v, v.upper()))
                for v, W, H in jobs]
    for _, dst_j, _, _, _ in all_jobs:
        dst_j.mkdir(parents=True, exist_ok=True)
        # Clear existing frames before re-processing
        for old_f in dst_j.glob("*.jpg"):
            old_f.unlink(missing_ok=True)
        for old_f in dst_j.glob("*.jpeg"):
            old_f.unlink(missing_ok=True)

    _allow_upscale = allow_upscale
    _enhance_flag  = enhance

    def _auto_enhance(img):
        """Apply auto-enhancement: brightness, contrast, sharpen, mild face smoothing."""
        from PIL import ImageEnhance, ImageOps, ImageFilter
        try:
            img = ImageOps.autocontrast(img, cutoff=1)
            img = ImageEnhance.Color(img).enhance(1.08)
            img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=3))
            try:
                import cv2, numpy as np
                arr = np.array(img)
                bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                smoothed = cv2.bilateralFilter(bgr, d=5, sigmaColor=25, sigmaSpace=25)
                blended = cv2.addWeighted(smoothed, 0.6, bgr, 0.4, 0)
                arr = cv2.cvtColor(blended, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(arr)
            except ImportError:
                pass
            except Exception:
                pass
            return img
        except Exception:
            return img

    from flask import current_app as _ca
    app = _ca._get_current_object()
    _user_id   = current_user.id
    _event_id = event_id

    def blur_bg(img, W, H):
        from PIL import ImageEnhance
        bg = img.resize((W, H), Image.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=25))
        return ImageEnhance.Brightness(bg).enhance(0.45)

    def fit_onto(img, cw, ch):
        return crop_fill(img, cw, ch)

    def detect_faces(scaled_img):
        try:
            import cv2, numpy as np
            cv_img = cv2.cvtColor(np.array(scaled_img), cv2.COLOR_RGB2BGR)
            gray   = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            faces = cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4,
                minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE)
            if len(faces) > 0:
                import numpy as np2
                fx = int(np2.mean([f[0]+f[2]//2 for f in faces]))
                fy = int(np2.mean([f[1]+f[3]//2 for f in faces]))
                return fx, fy
        except ImportError:
            pass
        except Exception:
            pass
        return None

    def crop_fill(img, cw, ch):
        iw, ih = img.size
        scale = max(cw/iw, ch/ih)
        if scale > 1.0 and not _allow_upscale:
            scale = 1.0
        elif scale > 1.5:
            app.logger.warning(f"Upscaling {iw}x{ih} by {scale:.1f}x to {cw}x{ch}")
        nw, nh = int(iw*scale), int(ih*scale)
        resample = Image.LANCZOS if scale <= 4.0 else Image.BICUBIC
        scaled = img.resize((nw, nh), resample)
        face_center = detect_faces(scaled)
        if nw > cw:
            fx = face_center[0] if face_center else nw//2
            x = max(0, min(fx - cw//2, nw - cw))
            scaled = scaled.crop((x, 0, x+cw, nh))
            nw = cw
        if nh > ch:
            fy = face_center[1] if face_center else nh//2
            y = max(0, min(fy - ch//2, nh - ch))
            scaled = scaled.crop((0, y, nw, y+ch))
        return scaled

    def stitch_h(img1, img2, W, H):
        hw = W//2
        c = Image.new("RGB", (W, H))
        c.paste(crop_fill(img1, hw, H), (0, 0))
        c.paste(crop_fill(img2, hw, H), (hw, 0))
        return c

    def stitch_v(img1, img2, W, H):
        hh = H//2
        c = Image.new("RGB", (W, H))
        c.paste(crop_fill(img1, W, hh), (0, 0))
        c.paste(crop_fill(img2, W, hh), (0, hh))
        return c

    def process_job(items, job_dst, job_W, job_H, pfx, job_version=None, _r2_user_id=None, _r2_event_id=None):
        target_landscape = job_W > job_H
        frame_num = 0
        i = 0
        while i < len(items):
            fname, img, is_portrait = items[i]
            uid = fname.rsplit(".", 1)[0]  # source UUID without extension
            try:
                if target_landscape and is_portrait:
                    if (i+1) < len(items) and items[i+1][2]:
                        out  = stitch_h(img, items[i+1][1], job_W, job_H)
                        name = f"{pfx}_{frame_num+1:04d}_{uid}.jpg"
                        i += 2
                    else:
                        out  = stitch_h(img, img, job_W, job_H)
                        name = f"{pfx}_{frame_num+1:04d}_{uid}__solo.jpg"
                        i += 1
                elif not target_landscape and not is_portrait:
                    if (i+1) < len(items) and not items[i+1][2]:
                        out  = stitch_v(img, items[i+1][1], job_W, job_H)
                        name = f"{pfx}_{frame_num+1:04d}_{uid}.jpg"
                        i += 2
                    else:
                        out  = stitch_v(img, img, job_W, job_H)
                        name = f"{pfx}_{frame_num+1:04d}_{uid}__solo.jpg"
                        i += 1
                else:
                    out  = fit_onto(img, job_W, job_H)
                    name = f"{pfx}_{frame_num+1:04d}_{uid}.jpg"
                    i += 1
                frame_num += 1
                # Upload frame to R2
                try:
                    import io as _io
                    from app.services import r2 as _R2
                    buf = _io.BytesIO()
                    out.save(buf, "JPEG", quality=92)
                    frame_bytes = buf.getvalue()
                    _R2.upload_bytes(
                        _R2.processed_key(_r2_user_id, _r2_event_id, job_version, name),
                        frame_bytes, "image/jpeg"
                    )
                    # Upload thumbnail
                    thumb = out.copy()
                    thumb.thumbnail((320, 180), Image.LANCZOS)
                    tbuf = _io.BytesIO()
                    thumb.save(tbuf, "JPEG", quality=75)
                    _R2.upload_bytes(
                        _R2.processed_thumb_key(_r2_user_id, _r2_event_id, job_version, name),
                        tbuf.getvalue(), "image/jpeg"
                    )
                except Exception as _e:
                    log(f"R2 upload error for {name}: {_e}")
            except Exception as e:
                log(f"ERROR frame {fname}: {e}")
                i += 1
        return frame_num

    from pathlib import Path
    import datetime
    # Log file in local temp dir (R2 mode has no local event dirs)
    import tempfile as _tmp_log
    from pathlib import Path as _Path2
    import pathlib as _pl2
    _log_dir = _pl2.Path(_tmp_log.gettempdir()) / "slideshow_logs"
    _log_dir.mkdir(exist_ok=True)
    log_path = _log_dir / f"{event_id}.log"
    log_path_str = str(log_path)

    def log(msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        app.logger.info(msg)
        try:
            with open(log_path_str, 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception:
            pass


    def run():
        import datetime as _dt, io
        from app.services import r2 as R2

        separator = f"\n{'='*60}\n[{_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] NEW BATCH STARTED\n{'='*60}\n"
        try:
            with open(log_path_str, 'a', encoding='utf-8') as f:
                f.write(separator)
        except Exception:
            pass
        log(f"Started processing {len(items_data)} photos × {len(all_jobs)} versions")

        # Download originals from R2 to temp dir
        import uuid as _uuid
        tmp_dir = Path(current_app.config.get("TEMP_DIR", "/tmp")) / f"proc_{_uuid.uuid4().hex[:8]}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        log(f"Temp dir: {tmp_dir}")

        items = []
        for fname, _ in items_data:
            try:
                key = R2.photo_key(_user_id, _event_id, fname)
                tmp_path = tmp_dir / fname
                R2.download_file(key, tmp_path)
                img = Image.open(str(tmp_path)).convert("RGB")
                if _enhance_flag:
                    img = _auto_enhance(img)
                items.append((fname, img, img.height > img.width))
            except Exception as e:
                log(f"ERROR loading {fname}: {e}")

        landscape_count = sum(1 for _,_,p in items if not p)
        portrait_count  = sum(1 for _,_,p in items if p)
        log(f"Loaded {len(items)} images from R2: {landscape_count} landscape, {portrait_count} portrait")
        # Pass R2 context to process_job
        _r2_user_id = _user_id
        _r2_event_id = _event_id

        for job_version, job_dst, job_W, job_H, job_pfx in all_jobs:
            log(f"--- {job_version} ({job_W}x{job_H}) ---")
            n = process_job(items, job_dst, job_W, job_H, job_pfx, job_version,
                           _r2_user_id, _r2_event_id)
            log(f"    {job_version}: {n} frames uploaded to R2")

        # Cleanup temp dir
        import shutil
        shutil.rmtree(str(tmp_dir), ignore_errors=True)
        log("DONE")

    def bg():
        with app.app_context():
            run()

    threading.Thread(target=bg, daemon=True).start()

    job_labels = ", ".join([f"{v} ({W}x{H})" for v,W,H in jobs])
    return jsonify({
        "ok": True,
        "jobs": [v for v,W,H in jobs],
        "count": len(photos),
        "message": f"Processing {len(photos)} photos × {len(jobs)} versions: {job_labels}"
    })


@bp.route("/<event_id>/process/status")
@login_required
def process_status(event_id):
    """Check processing status - count frames per version."""
    from app.services.storage import processed_dir as proc_dir
    db.session.query(Event)      .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    result = {}
    base = proc_dir(current_user.id, event_id)
    if base.exists():
        for ver_dir in sorted(base.iterdir()):
            if ver_dir.is_dir():
                files = [f.name for f in ver_dir.glob("*.jpg")]
                if files:
                    result[ver_dir.name] = len(files)
    return jsonify({"versions": result})


@bp.route("/<event_id>/process/log")
@login_required
def process_log(event_id):
    """Return current processing log content."""
    from app.services.storage import processed_dir as proc_dir
    db.session.query(Event)      .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    import tempfile as _tl
    import pathlib as _pl
    log_path = _pl.Path(_tl.gettempdir()) / "slideshow_logs" / f"{event_id}.log"
    if not log_path.exists():
        return jsonify({"log": None, "done": False})
    try:
        text = log_path.read_text(encoding='utf-8')
        done = text.strip().endswith('DONE')
        return jsonify({"log": text, "done": done})
    except Exception:
        return jsonify({"log": None, "done": False})


@bp.route("/<event_id>/process/frames")
@login_required
def process_frames(event_id):
    """Return processed frame filenames grouped by version for AJAX refresh."""
    from app.services.storage import processed_dir as proc_dir
    db.session.query(Event)      .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    result = {}
    base = proc_dir(current_user.id, event_id)
    if base.exists():
        for ver_dir in sorted(base.iterdir()):
            if ver_dir.is_dir():
                files = sorted([f.name for f in ver_dir.glob("*.jpg")])
                if files:
                    result[ver_dir.name] = files
    return jsonify({
        "versions": result,
        "user_id": current_user.id,
        "event_id": event_id
    })




@bp.route("/<event_id>/versions-r2")
@login_required
def list_r2_versions(event_id):
    """List processed versions available in R2 for rendering."""
    from app.services.storage import list_processed_versions_r2
    db.session.query(Event)\
      .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    versions = list_processed_versions_r2(current_user.id, event_id)
    return jsonify({"versions": list(versions.keys())})


@bp.route("/<event_id>/render-mp4", methods=["POST"])
@login_required
def render_mp4(event_id):
    """Render processed frames + audio clips into MP4 using ffmpeg."""
    import threading, subprocess, datetime, tempfile, shutil
    from pathlib import Path
    from app.services.storage import processed_dir, output_dir as _output_dir

    evt = db.session.query(Event)\
             .filter_by(id=event_id, user_id=current_user.id).first_or_404()

    data     = request.json or {}
    version  = data.get("version", "hd-landscape")
    playlist_id = data.get("playlist_id")
    duration = float(data.get("duration", 4.0))
    from app.models import log_activity
    log_activity(evt, "render_started", {"version": version, "playlist_id": playlist_id, "duration": duration})

    from app.services import r2 as R2
    from app.services.storage import list_processed_versions_r2
    versions_map = list_processed_versions_r2(current_user.id, event_id)
    frame_names = versions_map.get(version, [])
    if not frame_names:
        return jsonify({"error": f"No frames in {version}. Process photos first."}), 400

    clips = []
    if playlist_id:
        from app.models.audio import Playlist
        label = db.session.get(Playlist, int(playlist_id))
        if label and label.user_id == current_user.id:
            for c in label.clips:
                clips.append({
                    "r2_key": R2.audio_key(current_user.id, c.song.filename),
                    "filename": c.song.filename,
                    "start": c.trim_start or 0,
                    "end":   c.trim_end,
                    "name":  c.name
                })

    _safe_evt_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in (evt.name or "event"))[:60]
    out_name = f"{version}_{_safe_evt_name}.mp4"
    _user_id = current_user.id
    _event_id = event_id
    _frame_names = frame_names
    import tempfile as _tmp_r
    _rlog_dir = Path(_tmp_r.gettempdir()) / "slideshow_logs"
    _rlog_dir.mkdir(exist_ok=True)
    log_path = _rlog_dir / f"{event_id}.log"
    ffmpeg   = current_app.config.get("FFMPEG_PATH", "ffmpeg")
    app_obj  = current_app._get_current_object()

    def log(msg):
        ts2  = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts2}] {msg}\n"
        try:
            with open(str(log_path), 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception:
            pass


    def run():
        from app.services import r2 as R2
        tmp = Path(tempfile.mkdtemp())
        out_file = tmp / out_name

        # Download frames from R2 first
        frame_dir = tmp / "frames"
        frame_dir.mkdir(exist_ok=True)
        local_frames = []
        for fname in _frame_names:
            key = R2.processed_key(_user_id, _event_id, version, fname)
            local_path = frame_dir / fname
            try:
                R2.download_file(key, local_path)
                local_frames.append(local_path)
            except Exception:
                pass

        # Download audio clips from R2
        if clips:
            for cl in clips:
                audio_path = tmp / cl["filename"]
                try:
                    R2.download_file(cl["r2_key"], audio_path)
                    cl["path"] = str(audio_path)
                except Exception:
                    cl["path"] = None
            clips[:] = [c for c in clips if c.get("path")]

        frames = [str(fp) for fp in local_frames]

        try:
            log("=" * 55)
            log(f"RENDER: {version} → {out_file.name}")
            log(f"Frames: {len(frames)} × {duration}s | Clips: {len(clips)}")

            # --- Frame concat list ---
            concat_v = tmp / "frames.txt"
            with open(str(concat_v), 'w') as f:
                for fr in frames:
                    f.write(f"file '{fr}'\n")
                    f.write(f"duration {duration}\n")
                f.write(f"file '{frames[-1]}'\n")

            # --- Audio: extract + concat clips ---
            mixed = None
            if clips:
                log("Building audio...")
                parts = []
                for ci, cl in enumerate(clips):
                    part = tmp / f"c{ci}.wav"
                    cmd  = [ffmpeg, "-y", "-i", cl["path"],
                            "-ss", str(cl["start"])]
                    if cl["end"]:
                        cmd += ["-t", str(cl["end"] - cl["start"])]
                    cmd += ["-ar", "44100", "-ac", "2", str(part)]
                    r = subprocess.run(cmd, capture_output=True)
                    if r.returncode == 0:
                        parts.append(part)
                    else:
                        log(f"  clip {ci+1} error: {r.stderr.decode()[:80]}")

                if parts:
                    concat_a = tmp / "audio.txt"
                    with open(str(concat_a), 'w') as f:
                        for p in parts:
                            f.write(f"file '{p}'\n")
                    mixed = tmp / "audio.wav"
                    subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0",
                                    "-i", str(concat_a), "-c", "copy", str(mixed)],
                                   capture_output=True)
                    log(f"Audio ready: {len(parts)} clips")

            # --- ffmpeg render ---
            log("Running ffmpeg...")
            cmd = [ffmpeg, "-y",
                   "-f", "concat", "-safe", "0", "-i", str(concat_v)]
            if mixed and mixed.exists():
                cmd += ["-i", str(mixed)]
            cmd += ["-vf", "fps=25,format=yuv420p",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18"]
            if mixed and mixed.exists():
                cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
            cmd.append(str(out_file))

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True,
                                    bufsize=1)
            for line in proc.stdout:
                l = line.strip()
                if any(k in l for k in ["frame=", "time=", "error", "Error"]):
                    log(f"  {l}")
            proc.wait()

            if proc.returncode == 0 and out_file.exists():
                mb = out_file.stat().st_size / 1048576
                log(f"Rendered locally: {mb:.1f} MB. Uploading to R2...")
                # Upload output MP4 to R2
                try:
                    out_key = R2.output_key(_user_id, _event_id, out_name)
                    R2.upload_file(out_key, str(out_file), "video/mp4")
                    log(f"DONE - {out_name} ({mb:.1f} MB) uploaded to R2")
                except Exception as e:
                    log(f"R2 upload error: {e}")
            else:
                log(f"FAILED - ffmpeg exit {proc.returncode}")

        except Exception as e:
            log(f"RENDER ERROR: {e}")
        finally:
            shutil.rmtree(str(tmp), ignore_errors=True)

    def bg():
        with app_obj.app_context():
            run()

    threading.Thread(target=bg, daemon=True).start()

    return jsonify({
        "ok": True,
        "output": out_name,
        "frames": len(frame_names),
        "clips":  len(clips),
        "duration": duration,
        "version": version
    })


@bp.route("/<event_id>/output-files")
@login_required
def list_output_files(event_id):
    """List rendered MP4 files for this event (from R2)."""
    from app.services import r2 as R2
    db.session.query(Event)\
      .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    files = []
    try:
        client = R2.get_client()
        prefix = f"users/{current_user.id}/events/{event_id}/output/"
        resp = client.list_objects_v2(Bucket=R2.bucket(), Prefix=prefix)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            fname = key.split("/")[-1]
            if fname.endswith(".mp4"):
                files.append({
                    "name": fname,
                    "size_mb": round(obj["Size"] / 1048576, 1),
                    "url": f"/events/{event_id}/download/{fname}"
                })
        files.sort(key=lambda x: x["name"], reverse=True)
    except Exception as e:
        current_app.logger.error(f"list_output_files R2 error: {e}")
    return jsonify({"files": files})


@bp.route("/<event_id>/download/<filename>")
@login_required
def download_output(event_id, filename):
    """Download rendered MP4 from R2 via presigned URL with force-download header."""
    from app.services import r2 as R2
    from flask import redirect
    db.session.query(Event)\
      .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    key = R2.output_key(current_user.id, event_id, filename)
    # Add ResponseContentDisposition to force download instead of inline play
    url = R2.get_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": R2.bucket(),
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=3600,
    )
    return redirect(url)


# ── Share token management ────────────────────────────────────────────────────

# ─── Captions ─────────────────────────────────────────────────────────────
@bp.route("/<event_id>/caption/event", methods=["POST"])
@login_required
def save_event_caption(event_id):
    """Persist the event-level caption (reuses title_text / title_subtitle)."""
    evt = db.session.query(Event)\
             .filter_by(id=event_id, user_id=current_user.id).first_or_404()

    data = request.json or {}
    title    = (data.get("title_text") or "").strip()
    subtitle = (data.get("title_subtitle") or "").strip()

    evt.title_text     = title or None
    evt.title_subtitle = subtitle or None

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"ok": False, "error": "Database error"}), 500

    from app.models import log_activity
    log_activity(evt, "caption.event_saved", {"title": title, "subtitle": subtitle})
    return jsonify({
        "ok": True,
        "title_text": evt.title_text,
        "title_subtitle": evt.title_subtitle,
    })


@bp.route("/<event_id>/caption/photo/<int:photo_id>", methods=["POST"])
@login_required
def save_photo_caption(event_id, photo_id):
    """Persist a single photo's caption."""
    from app.models.photo import Photo
    evt = db.session.query(Event)\
             .filter_by(id=event_id, user_id=current_user.id).first_or_404()

    photo = db.session.query(Photo).filter_by(id=photo_id, event_id=event_id).first()
    if photo is None:
        return jsonify({"ok": False, "error": "Photo not found"}), 404

    data = request.json or {}
    caption = (data.get("caption") or "").strip()
    photo.caption = caption or None

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"ok": False, "error": "Database error"}), 500

    from app.models import log_activity
    log_activity(evt, "caption.photo_saved", {"photo_id": photo_id, "caption": caption})
    return jsonify({"ok": True, "id": photo.id, "caption": photo.caption})


@bp.route("/<event_id>/caption/photos/bulk", methods=["POST"])
@login_required
def save_photo_captions_bulk(event_id):
    """Persist multiple photo captions in one round-trip."""
    from app.models.photo import Photo
    evt = db.session.query(Event)\
             .filter_by(id=event_id, user_id=current_user.id).first_or_404()

    data  = request.json or {}
    items = data.get("captions") or []
    if not isinstance(items, list):
        return jsonify({"ok": False, "error": "Invalid payload"}), 400

    photos = {p.id: p for p in db.session.query(Photo).filter_by(event_id=event_id).all()}
    changed = 0
    for item in items:
        pid = (item or {}).get("id")
        if pid in photos:
            photos[pid].caption = ((item.get("caption") or "").strip()) or None
            changed += 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"ok": False, "error": "Database error"}), 500

    from app.models import log_activity
    log_activity(evt, "caption.photos_bulk_saved", {"count": changed})
    return jsonify({"ok": True, "saved": changed})


@bp.route("/<event_id>/share", methods=["POST"])
@login_required
def create_share_token(event_id):
    """Generate a public share token for this event."""
    import secrets, json
    from app.models.event import ShareToken
    evt = db.session.query(Event)\
             .filter_by(id=event_id, user_id=current_user.id).first_or_404()

    # Reuse existing active share for this event if one exists
    from datetime import datetime
    existing = db.session.query(ShareToken)\
                 .filter_by(event_id=evt.id, share_type="public")\
                 .order_by(ShareToken.created_at.desc()).first()
    if existing and (not existing.expires_at or existing.expires_at > datetime.utcnow()):
        from flask import request as _req0
        scheme = _req0.headers.get("X-Forwarded-Proto") or _req0.scheme
        absolute_url = f"{scheme}://{_req0.host}/s/{existing.token}"
        return jsonify({
            "ok": True,
            "reused": True,
            "token": existing.token,
            "url": f"/s/{existing.token}",
            "absolute_url": absolute_url,
            "password": existing.plain_password or "WELCOME",
        })

    data       = request.json or {}
    expires_in    = data.get("expires_days")   # None = no expiry
    playlist_ids  = data.get("playlist_ids")   # None = all playlists
    version       = data.get("version")        # default processed version
    versions_list = data.get("versions_list")  # list of versions viewer can pick from
    password      = (data.get("password") or "").strip() or "WELCOME"
    description   = data.get("description")

    from datetime import datetime, timedelta
    token = secrets.token_urlsafe(24)
    share = ShareToken(
        token          = token,
        event_id       = evt.id,
        created_by     = current_user.id,
        share_type     = "public",
        role           = "viewer",
        version        = version,
        versions_list  = json.dumps(versions_list) if versions_list else None,
        playlist_ids   = json.dumps(playlist_ids) if playlist_ids else None,
        plain_password = password,
        description    = description,
        expires_at     = datetime.utcnow() + timedelta(days=int(expires_in))
                          if expires_in else None,
    )
    db.session.add(share)
    db.session.commit()
    from app.models import log_activity
    log_activity(evt, "share_created", {"token": token, "description": description or "", "has_password": bool(password)})
    from flask import request as _req
    scheme = _req.headers.get("X-Forwarded-Proto") or _req.scheme
    host   = _req.host
    absolute_url = f"{scheme}://{host}/s/{token}"
    return jsonify({"ok": True, "token": token, "url": f"/s/{token}", "absolute_url": absolute_url, "password": password})


@bp.route("/<event_id>/share", methods=["GET"])
@login_required
def list_share_tokens(event_id):
    """List existing share tokens for this event."""
    from app.models.event import ShareToken
    evt = db.session.query(Event)\
             .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    tokens = evt.share_tokens.filter_by(share_type="public")\
                               .order_by(ShareToken.created_at.desc()).all()
    return jsonify({"tokens": [
        {"token": t.token, "url": t.public_url,
         "created_at": t.created_at.strftime("%Y-%m-%d %H:%M"),
         "expires_at": t.expires_at.strftime("%Y-%m-%d") if t.expires_at else None,
         "use_count": t.use_count, "version": t.version}
        for t in tokens
    ]})


@bp.route("/<event_id>/share/<token>/password", methods=["POST"])
@login_required
def update_share_password(event_id, token):
    """Update password on an existing share token."""
    import hashlib, requests as req_lib, json
    from app.models.event import ShareToken
    db.session.query(Event)      .filter_by(id=event_id, user_id=current_user.id).first_or_404()

    data     = request.json or {}
    password = data.get('password', 'WELCOME')
    pw_hash  = hashlib.sha256(password.encode()).hexdigest()

    cf_account = current_app.config.get("CF_ACCOUNT_ID")
    cf_token   = current_app.config.get("CF_API_TOKEN")
    cf_d1_id   = current_app.config.get("CF_D1_ID")

    # Update D1
    try:
        req_lib.post(
            f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/d1/database/{cf_d1_id}/query",
            headers={"Authorization": f"Bearer {cf_token}", "Content-Type": "application/json"},
            json={"sql": "UPDATE slideshow_tokens SET password_hash=? WHERE token=?",
                  "params": [pw_hash, token]},
            timeout=10
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Update local SQLite
    st = db.session.query(ShareToken).filter_by(token=token).first()
    if st:
        st.plain_password = password
        db.session.commit()

    return jsonify({"ok": True})


@bp.route("/<event_id>/share/<token>", methods=["DELETE"])
@login_required
def revoke_share_token(event_id, token):
    """Revoke a share token."""
    from app.models.event import ShareToken
    db.session.query(Event)\
      .filter_by(id=event_id, user_id=current_user.id).first_or_404()
    st = db.session.query(ShareToken).filter_by(token=token, event_id=event_id).first_or_404()
    db.session.delete(st)
    db.session.commit()
    return jsonify({"ok": True})


# ── Share to Cloudflare R2 ────────────────────────────────────────────────────

@bp.route("/<event_id>/share-cloud", methods=["POST"])
@login_required
def share_to_cloud(event_id):
    """Upload ALL processed versions + audio to R2. One link, all versions."""
    import threading, secrets, json
    from app.services.storage import processed_dir, audio_dir
    from app.models.audio import Playlist

    evt = db.session.query(Event)             .filter_by(id=event_id, user_id=current_user.id).first_or_404()

    data         = request.json or {}
    playlist_ids    = data.get("playlist_ids")
    expires_days = data.get("expires_days")
    force_upload = data.get("force_upload", False)
    password     = data.get("password") or "WELCOME"
    description  = data.get("description") or ""

    cf_account = current_app.config.get("CF_ACCOUNT_ID")
    cf_token   = current_app.config.get("CF_API_TOKEN")
    cf_bucket  = current_app.config.get("CF_R2_BUCKET", "slideshow-studio")
    cf_d1_id   = current_app.config.get("CF_D1_ID")
    cf_r2_key  = current_app.config.get("CF_R2_ACCESS_KEY_ID", "")
    cf_r2_sec  = current_app.config.get("CF_R2_SECRET_ACCESS_KEY", "")
    cf_r2_ep   = current_app.config.get("CF_R2_ENDPOINT",
                   f"https://{cf_account}.r2.cloudflarestorage.com")

    if not all([cf_account, cf_d1_id, cf_r2_key, cf_r2_sec]):
        return jsonify({"error": "Cloudflare not configured in .env"}), 400

    # Scan ALL processed versions
    proc_base = processed_dir(current_user.id, event_id)
    all_versions = {}
    if proc_base.exists():
        for ver_dir in sorted(proc_base.iterdir()):
            if ver_dir.is_dir() and ver_dir.name != "thumbs":
                frames = sorted([f.name for f in ver_dir.iterdir()
                                 if f.suffix == ".jpg" and f.parent == ver_dir])
                if frames:
                    all_versions[ver_dir.name] = {"frames": frames, "path": ver_dir}

    if not all_versions:
        return jsonify({"error": "No processed frames found. Process photos first."}), 400

    # Get labels
    labels_q = db.session.query(Playlist).filter_by(user_id=current_user.id)
    if playlist_ids:
        labels_q = labels_q.filter(Playlist.id.in_(playlist_ids))
    labels = labels_q.all()

    clips_by_label = {}
    audio_files = set()
    for label in labels:
        clips = []
        for c in label.clips:
            clips.append({"id": c.id, "name": c.display_name,
                          "file": c.song.filename, "start": c.start_s or 0, "end": c.end_s})
            audio_files.add(c.song.filename)
        clips_by_label[label.id] = {"name": label.name, "clips": clips}

    # Check if existing token exists for this event
    existing = None
    try:
        import requests as req_lib
        check = req_lib.post(
            f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/d1/database/{cf_d1_id}/query",
            headers={"Authorization": f"Bearer {cf_token}", "Content-Type": "application/json"},
            json={"sql": "SELECT token FROM slideshow_tokens WHERE event_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
                  "params": [event_id, current_user.id]},
            timeout=10
        ).json()
        rows = check.get("result", [{}])[0].get("results", [])
        if rows:
            existing = rows[0]["token"]
    except Exception:
        pass

    token = existing if existing and not force_upload else secrets.token_urlsafe(24)

    from datetime import datetime, timedelta
    expires_at = (datetime.utcnow() + timedelta(days=int(expires_days))).isoformat() if expires_days else None

    # Default version — prefer hd-landscape, then any hd-*, then first landscape, then first
    ver_keys = list(all_versions.keys())
    default_version = (
        next((v for v in ver_keys if v == 'hd-landscape'), None) or
        next((v for v in ver_keys if v.startswith('hd')), None) or
        next((v for v in ver_keys if 'landscape' in v), None) or
        ver_keys[0]
    )

    meta = {
        "event_name":     evt.name,
        "versions":         {v: d["frames"] for v, d in all_versions.items()},
        "default_version":  default_version,
        "labels":           [{"id": str(l.id), "name": l.name} for l in labels],
        "default_playlist_id": str(labels[0].id) if labels else "",
    }

    import tempfile as _tmp_s
    _slog_dir = Path(_tmp_s.gettempdir()) / "slideshow_logs"
    _slog_dir.mkdir(exist_ok=True)
    log_path = _slog_dir / f"{event_id}.log"
    app_obj  = current_app._get_current_object()
    user_id  = current_user.id

    def log(msg):
        from datetime import datetime as _dt
        try:
            with open(str(log_path), 'a', encoding='utf-8') as f:
                f.write(f"[{_dt.now().strftime('%H:%M:%S')}] {msg}\n")
        except Exception:
            pass

    import hashlib as _hl
    password_hash = _hl.sha256((password or 'WELCOME').encode()).hexdigest()

    def run():
        try:
            import boto3
            from botocore.config import Config
            s3 = boto3.client("s3", endpoint_url=cf_r2_ep,
                              aws_access_key_id=cf_r2_key,
                              aws_secret_access_key=cf_r2_sec,
                              config=Config(signature_version="s3v4"),
                              region_name="auto")
        except Exception as e:
            log(f"boto3 error: {e}"); return

        log("=" * 55)
        log(f"CLOUD SHARE: {evt.name} → share.calgarydhamaka.com/s/{token}")
        log(f"Versions: {list(all_versions.keys())}")

        total_frames = sum(len(d["frames"]) for d in all_versions.values())
        log(f"Total: {total_frames} frames across {len(all_versions)} versions")

        # Upload each version
        for ver, vdata in all_versions.items():
            frames = vdata["frames"]
            ver_path = vdata["path"]

            # Check if already uploaded
            try:
                s3.head_object(Bucket=cf_bucket,
                               Key=f"{user_id}/{event_id}/{ver}/{frames[0]}")
                log(f"  {ver}: already in R2, skipping")
                continue
            except Exception:
                pass

            log(f"  Uploading {ver} ({len(frames)} frames)...")
            done = 0
            for fname in frames:
                fpath = ver_path / fname
                try:
                    with open(str(fpath), 'rb') as f:
                        s3.put_object(Bucket=cf_bucket,
                                      Key=f"{user_id}/{event_id}/{ver}/{fname}",
                                      Body=f.read(), ContentType="image/jpeg")
                    done += 1
                except Exception as e:
                    log(f"    ERROR {fname}: {e}")

            # Upload thumbnails
            thumb_dir = ver_path / "thumbs"
            if thumb_dir.exists():
                for tf in thumb_dir.glob("*.jpg"):
                    try:
                        with open(str(tf), 'rb') as f:
                            s3.put_object(Bucket=cf_bucket,
                                          Key=f"{user_id}/{event_id}/{ver}/thumbs/{tf.name}",
                                          Body=f.read(), ContentType="image/jpeg")
                    except Exception:
                        pass
            log(f"  {ver}: {done}/{len(frames)} frames uploaded")

        # Upload audio
        audio_base = audio_dir(user_id, "original")
        for fname in audio_files:
            apath = audio_base / fname
            if not apath.exists():
                continue
            try:
                s3.head_object(Bucket=cf_bucket,
                               Key=f"{user_id}/{event_id}/audio/{fname}")
            except Exception:
                try:
                    with open(str(apath), 'rb') as f:
                        s3.put_object(Bucket=cf_bucket,
                                      Key=f"{user_id}/{event_id}/audio/{fname}",
                                      Body=f.read(), ContentType="audio/mpeg")
                except Exception as e:
                    log(f"  Audio error {fname}: {e}")
        log(f"  Audio: {len(audio_files)} files checked/uploaded")

        # Upsert D1 token
        try:
            import requests as req_lib
            d1_url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/d1/database/{cf_d1_id}/query"
            d1_hdr = {"Authorization": f"Bearer {cf_token}", "Content-Type": "application/json"}

            req_lib.post(d1_url, headers=d1_hdr, json={
                "sql": "INSERT OR REPLACE INTO slideshow_tokens (token,event_id,user_id,event_name,meta_json,expires_at,password_hash) VALUES (?,?,?,?,?,?,?)",
                "params": [token, event_id, user_id, evt.name, json.dumps(meta), expires_at, password_hash]
            }, timeout=15)

            for lid, ldata in clips_by_label.items():
                req_lib.post(d1_url, headers=d1_hdr, json={
                    "sql": "INSERT OR REPLACE INTO slideshow_clips (token,playlist_id,label_name,clips_json) VALUES (?,?,?,?)",
                    "params": [token, str(lid), ldata["name"], json.dumps(ldata["clips"])]
                }, timeout=15)

            log(f"Token saved: {token}")
            log(f"DONE ✓ https://share.calgarydhamaka.com/s/{token}")

            # Save locally in SQLite for owner reference
            try:
                from app.models.event import ShareToken
                existing_local = db.session.query(ShareToken).filter_by(token=token).first()
                if existing_local:
                    existing_local.description   = description or existing_local.description
                    existing_local.plain_password = password or existing_local.plain_password
                    existing_local.versions_list  = json.dumps(list(all_versions.keys()))
                else:
                    st = ShareToken(
                        token          = token,
                        event_id     = event_id,
                        created_by     = user_id,
                        share_type     = "public",
                        description    = description,
                        plain_password = password,
                        versions_list  = json.dumps(list(all_versions.keys())),
                        expires_at     = datetime.fromisoformat(expires_at) if expires_at else None,
                    )
                    db.session.add(st)
                db.session.commit()
            except Exception as e:
                log(f"Local DB save error: {e}")
        except Exception as e:
            log(f"D1 error: {e}")

    def bg():
        with app_obj.app_context():
            run()

    threading.Thread(target=bg, daemon=True).start()

    return jsonify({
        "ok": True, "token": token,
        "url": f"https://share.calgarydhamaka.com/s/{token}",
        "versions": list(all_versions.keys()),
        "reused_token": existing == token
    })

