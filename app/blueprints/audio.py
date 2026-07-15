from flask       import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from app.extensions  import db
from app.models.audio import AudioFile, AudioClip, AudioLabel, SongFolder
from app.services.storage import save_uploaded_audio_r2 as save_uploaded_audio, audio_dir, delete_audio_files

bp = Blueprint("audio", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# SONG LIBRARY
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/")
@login_required
def index():
    songs        = db.session.query(AudioFile)\
                     .filter_by(user_id=current_user.id)\
                     .order_by(AudioFile.orig_name).all()
    labels       = db.session.query(AudioLabel)\
                     .filter_by(user_id=current_user.id)\
                     .order_by(AudioLabel.sort_order, AudioLabel.name).all()
    song_folders = db.session.query(SongFolder)\
                     .filter_by(user_id=current_user.id)\
                     .order_by(SongFolder.sort_order, SongFolder.name).all()
    return render_template("audio/index.html",
                           songs=songs, labels=labels, song_folders=song_folders)

@bp.route("/upload", methods=["POST"])
@login_required
def upload():
    f = request.files.get("audio")
    if not f:
        return jsonify({"error": "no file"}), 400
    result = save_uploaded_audio(f, current_user.id)
    folder_id = request.form.get("folder_id")
    if folder_id:
        folder = db.session.get(SongFolder, int(folder_id))
        if not folder or folder.user_id != current_user.id:
            folder_id = None

    song = AudioFile(
        user_id        = current_user.id,
        filename       = result["filename"],
        orig_name      = result["orig_name"],
        file_size      = result["file_size"],
        duration_s     = result.get("duration_s"),
        song_folder_id = int(folder_id) if folder_id else None,
    )
    db.session.add(song)
    db.session.flush()
    # Auto-create first clip: "Song Name - 1" with description "Full Song"
    base = song.orig_name.rsplit('.', 1)[0] if '.' in song.orig_name else song.orig_name
    clip = AudioClip(song_id=song.id, name=f"{base} - 1",
                     description="Full Song", trim_start="", trim_end="")
    db.session.add(clip)
    db.session.commit()
    return jsonify({"ok": True, "id": song.id,
                    "name": song.orig_name, "clip_id": clip.id})


@bp.route("/<int:song_id>/delete", methods=["POST"])
@login_required
def delete_song(song_id):
    song = db.session.get(AudioFile, song_id)
    if not song or song.user_id != current_user.id:
        abort(404)
    delete_audio_files(current_user.id, song.filename)
    db.session.delete(song)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/scan-durations", methods=["POST"])
@login_required
def scan_durations():
    songs = db.session.query(AudioFile).filter_by(user_id=current_user.id).all()
    updated = 0
    for song in songs:
        if song.duration_s:
            continue
        src = audio_dir(song.user_id, "original") / song.filename
        try:
            from mutagen import File as MF
            info = MF(str(src))
            if info and info.info:
                song.duration_s = round(info.info.length, 2)
                updated += 1
        except Exception:
            pass
    db.session.commit()
    return jsonify({"ok": True, "updated": updated})


# ─────────────────────────────────────────────────────────────────────────────
# SONG FOLDERS
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/song-folders", methods=["POST"])
@login_required
def create_song_folder():
    data  = request.json or {}
    name  = data.get("name", "").strip()[:100]
    color = data.get("color", "#1e3a52")
    if not name:
        return jsonify({"error": "name required"}), 400
    if db.session.query(SongFolder).filter_by(user_id=current_user.id, name=name).first():
        return jsonify({"error": "folder already exists"}), 409
    folder = SongFolder(user_id=current_user.id, name=name, color=color)
    db.session.add(folder)
    db.session.commit()
    return jsonify({"id": folder.id, "name": folder.name, "color": folder.color})


@bp.route("/song-folders/<int:folder_id>", methods=["PUT"])
@login_required
def update_song_folder(folder_id):
    folder = db.session.get(SongFolder, folder_id)
    if not folder or folder.user_id != current_user.id:
        abort(404)
    data = request.json or {}
    if "name"  in data: folder.name  = data["name"].strip()[:100]
    if "color" in data: folder.color = data["color"]
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/song-folders/<int:folder_id>", methods=["DELETE"])
@login_required
def delete_song_folder(folder_id):
    folder = db.session.get(SongFolder, folder_id)
    if not folder or folder.user_id != current_user.id:
        abort(404)
    # Move songs back to unorganised
    for song in folder.songs:
        song.song_folder_id = None
    db.session.delete(folder)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/<int:song_id>/song-folder", methods=["POST"])
@login_required
def assign_song_folder(song_id):
    song = db.session.get(AudioFile, song_id)
    if not song or song.user_id != current_user.id:
        abort(404)
    folder_id = (request.json or {}).get("folder_id")
    if folder_id:
        folder = db.session.get(SongFolder, folder_id)
        if not folder or folder.user_id != current_user.id:
            abort(404)
    song.song_folder_id = folder_id
    db.session.commit()
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────────────────
# CLIP LIBRARY
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/clips")
@login_required
def clips():
    songs        = db.session.query(AudioFile)\
                     .filter_by(user_id=current_user.id)\
                     .order_by(AudioFile.orig_name).all()
    labels       = db.session.query(AudioLabel)\
                     .filter_by(user_id=current_user.id)\
                     .order_by(AudioLabel.sort_order, AudioLabel.name).all()
    song_folders = db.session.query(SongFolder)\
                     .filter_by(user_id=current_user.id)\
                     .order_by(SongFolder.sort_order, SongFolder.name).all()
    labels_data = [{"id": l.id, "name": l.name} for l in labels]
    return render_template("audio/clips.html",
                           songs=songs, labels=labels, labels_data=labels_data, song_folders=song_folders)

@bp.route("/<int:song_id>/clips", methods=["GET"])
@login_required
def get_clips(song_id):
    song = db.session.get(AudioFile, song_id)
    if not song or song.user_id != current_user.id:
        abort(404)
    return jsonify([c.to_dict() for c in song.clips])


@bp.route("/<int:song_id>/clips", methods=["POST"])
@login_required
def create_clip(song_id):
    song = db.session.get(AudioFile, song_id)
    if not song or song.user_id != current_user.id:
        abort(404)
    data = request.json or {}

    # Auto-name: "Song Name - 2", "Song Name - 3" etc.
    if not data.get("name"):
        base = song.orig_name.rsplit('.', 1)[0] if '.' in song.orig_name else song.orig_name
        num  = len(song.clips) + 1   # clip 1 already exists (created on upload)
        name = f"{base} - {num}"
    else:
        name = data["name"].strip()[:100]

    # Auto-description: "Clip 1" for user's first manual clip after the
    # auto-created "Full Song" clip. Formula: current clip count is the
    # position number of the user's Nth manual clip (since Full Song is
    # position 1, user clip 1 is position 2 = current count of 1).
    user_clip_num = len(song.clips)  # count of clips before this insert
    default_desc = f"Clip {user_clip_num}" if user_clip_num > 0 else "Full Song"

    clip = AudioClip(
        song_id     = song_id,
        name        = name,
        description = data.get("description", "").strip() or default_desc,
        trim_start  = data.get("trim_start", ""),
        trim_end    = data.get("trim_end", ""),
        fade_in     = data.get("fade_in", False),
        fade_out    = data.get("fade_out", True),
        normalize   = data.get("normalize", False),
    )
    db.session.add(clip)
    db.session.commit()
    return jsonify(clip.to_dict())


@bp.route("/clips/<int:clip_id>", methods=["PUT"])
@login_required
def update_clip(clip_id):
    clip = db.session.get(AudioClip, clip_id)
    if not clip or clip.song.user_id != current_user.id:
        abort(404)
    data = request.json or {}
    if "name"        in data: clip.name        = str(data["name"]).strip()[:100]
    if "description" in data: clip.description = str(data["description"]).strip()[:200]
    if "trim_start" in data: clip.trim_start = data["trim_start"]
    if "trim_end"   in data: clip.trim_end   = data["trim_end"]
    if "fade_in"    in data: clip.fade_in    = bool(data["fade_in"])
    if "fade_out"   in data: clip.fade_out   = bool(data["fade_out"])
    if "normalize"  in data: clip.normalize  = bool(data["normalize"])
    db.session.commit()
    return jsonify(clip.to_dict())


@bp.route("/clips/<int:clip_id>", methods=["DELETE"])
@login_required
def delete_clip(clip_id):
    clip = db.session.get(AudioClip, clip_id)
    if not clip or clip.song.user_id != current_user.id:
        abort(404)
    if len(clip.song.clips) <= 1:
        return jsonify({"error": "Cannot delete the only clip — delete the song instead"}), 400
    db.session.delete(clip)
    db.session.commit()
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────────────────
# LABELS
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/labels")
@login_required
def labels_page():
    labels = db.session.query(AudioLabel)\
               .filter_by(user_id=current_user.id)\
               .order_by(AudioLabel.sort_order, AudioLabel.name).all()
    return render_template("audio/labels.html", labels=labels)


@bp.route("/labels", methods=["POST"])
@login_required
def create_label():
    data  = request.json or {}
    name  = data.get("name", "").strip()[:100]
    color = data.get("color", "#1e3a52")
    if not name:
        return jsonify({"error": "name required"}), 400
    if db.session.query(AudioLabel).filter_by(
            user_id=current_user.id, name=name).first():
        return jsonify({"error": "label already exists"}), 409
    label = AudioLabel(user_id=current_user.id, name=name, color=color)
    db.session.add(label)
    db.session.commit()
    return jsonify({"id": label.id, "name": label.name, "color": label.color})


@bp.route("/labels/<int:label_id>", methods=["PUT"])
@login_required
def update_label(label_id):
    label = db.session.get(AudioLabel, label_id)
    if not label or label.user_id != current_user.id:
        abort(404)
    data = request.json or {}
    if "name"  in data: label.name  = data["name"].strip()[:100]
    if "color" in data: label.color = data["color"]
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/labels/<int:label_id>", methods=["DELETE"])
@login_required
def delete_label(label_id):
    label = db.session.get(AudioLabel, label_id)
    if not label or label.user_id != current_user.id:
        abort(404)
    if label.is_project_label:
        return jsonify({"error": "Cannot delete a project label — delete the project instead"}), 400
    db.session.delete(label)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/labels/<int:label_id>/clips", methods=["POST"])
@login_required
def add_clip_to_label(label_id):
    """Add or remove a clip from a label."""
    label = db.session.get(AudioLabel, label_id)
    if not label or label.user_id != current_user.id:
        abort(404)
    data    = request.json or {}
    clip_id = data.get("clip_id")
    action  = data.get("action", "toggle")   # add | remove | toggle
    clip    = db.session.get(AudioClip, clip_id)
    if not clip or clip.song.user_id != current_user.id:
        abort(404)
    in_label = label in clip.labels
    if action == "add"    or (action == "toggle" and not in_label): clip.labels.append(label)
    elif action == "remove" or (action == "toggle" and in_label):   clip.labels.remove(label)
    db.session.commit()
    return jsonify({"ok": True, "in_label": label in clip.labels,
                    "clip_count": label.clip_count})


@bp.route("/labels/<int:label_id>/import/<int:source_label_id>", methods=["POST"])
@login_required
def import_from_label(label_id, source_label_id):
    """Import all clips from source label into target label."""
    target = db.session.get(AudioLabel, label_id)
    source = db.session.get(AudioLabel, source_label_id)
    if not target or target.user_id != current_user.id:
        abort(404)
    if not source or source.user_id != current_user.id:
        abort(404)
    added = 0
    for clip in source.clips:
        if label_id not in [l.id for l in clip.labels]:  # avoid duplicates
            clip.labels.append(target)
            added += 1
    db.session.commit()
    return jsonify({"ok": True, "added": added,
                    "total": target.clip_count})


# ─────────────────────────────────────────────────────────────────────────────
# CLIP EDITOR (shared between song and clip library)
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/<int:song_id>/clip-editor")
@login_required
def clip_editor(song_id):
    song = db.session.get(AudioFile, song_id)
    if not song or song.user_id != current_user.id:
        abort(404)
    labels = db.session.query(AudioLabel)\
               .filter_by(user_id=current_user.id)\
               .order_by(AudioLabel.name).all()
    audio_url = f"/api/v1/media/audio/{current_user.id}/original/{song.filename}"
    return render_template("audio/clip_editor.html",
                           audio_file=song, song=song,
                           audio_url=audio_url, labels=labels)

@bp.route("/stream/<int:song_id>")
@login_required
def stream_song(song_id):
    """Stream a song for HTML5 <audio> playback. Redirects to a
    short-lived presigned R2 URL so seek + range requests work
    natively without proxying bytes through Flask."""
    from app.models.audio import AudioFile
    from app.services import r2 as r2svc

    song = db.session.get(AudioFile, song_id)
    if not song or song.user_id != current_user.id:
        abort(404)

    key = r2svc.key_for_audio(song.user_id, song.filename)
    url = r2svc.presign_get(key, expires_in=600)  # 10 minutes
    return redirect(url)
