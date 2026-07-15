from flask       import Blueprint, render_template, request, jsonify, abort, redirect, url_for
from flask_login import login_required, current_user

from app.extensions      import db
from app.models.audio    import AudioFile, AudioClip, AudioLabel, Library, Playlist, PlaylistClip
from app.services.storage import (
    save_uploaded_audio_r2 as save_uploaded_audio,
    audio_dir,
    delete_audio_files,
)

bp = Blueprint("audio", __name__)


# -----------------------------------------------------------------------------
# SONG LIBRARY (main list page)
# -----------------------------------------------------------------------------
@bp.route("/")
@login_required
def index():
    songs     = db.session.query(AudioFile)\
                  .filter_by(user_id=current_user.id)\
                  .order_by(AudioFile.orig_name).all()
    labels    = db.session.query(AudioLabel)\
                  .filter_by(user_id=current_user.id)\
                  .order_by(AudioLabel.sort_order, AudioLabel.name).all()
    libraries = db.session.query(Library)\
                  .filter_by(user_id=current_user.id)\
                  .order_by(Library.sort_order, Library.name).all()
    return render_template("audio/index.html",
                           songs=songs, labels=labels, libraries=libraries)


# -----------------------------------------------------------------------------
# UPLOAD
# -----------------------------------------------------------------------------
@bp.route("/upload", methods=["POST"])
@login_required
def upload():
    """Upload an audio file.

    Contract:
    - Requires ``audio`` field (the file).
    - Accepts ``library_id`` field to place the song in a Library.
      If library_id is missing or invalid, we look for one owned by the user
      called "Unsorted" - creating it if needed (along with its default
      playlist). This keeps single-file uploads simple while still ensuring
      every song has a Library and a default Playlist for its auto-clip.
    """
    f = request.files.get("audio")
    if not f:
        return jsonify({"error": "no file"}), 400

    result = save_uploaded_audio(f, current_user.id)

    # Resolve target library
    library_id = request.form.get("library_id")
    library = None
    if library_id:
        library = db.session.get(Library, int(library_id))
        if not library or library.user_id != current_user.id:
            library = None

    if library is None:
        # Fallback: use or create "Unsorted" library
        library = Library.query.filter_by(
            user_id=current_user.id, name="Unsorted"
        ).first()
        if library is None:
            library = Library(
                user_id=current_user.id,
                name="Unsorted",
                color="#8A90A8",
                sort_order=999,
            )
            db.session.add(library)
            db.session.flush()
            # Auto-create default playlist for this Library
            default_pl = Playlist(
                user_id=current_user.id,
                library_id=library.id,
                name=library.name,
                color=library.color,
                sort_order=0,
                is_default=True,
            )
            db.session.add(default_pl)
            db.session.flush()

    # Ensure library has a default playlist (idempotent - existing libraries
    # created via the create-library route already have one)
    default_pl = Playlist.query.filter_by(
        library_id=library.id, is_default=True
    ).first()
    if default_pl is None:
        default_pl = Playlist(
            user_id=current_user.id,
            library_id=library.id,
            name=library.name,
            color=library.color,
            sort_order=0,
            is_default=True,
        )
        db.session.add(default_pl)
        db.session.flush()

    # Create the song
    song = AudioFile(
        user_id     = current_user.id,
        filename    = result["filename"],
        orig_name   = result["orig_name"],
        file_size   = result["file_size"],
        duration_s  = result.get("duration_s"),
        library_id  = library.id,
    )
    db.session.add(song)
    db.session.flush()

    # Auto-create the "Full Song" clip
    base = song.orig_name.rsplit(".", 1)[0] if "." in song.orig_name else song.orig_name
    clip = AudioClip(
        song_id     = song.id,
        name        = f"{base} - 1",
        description = "Full Song",
        trim_start  = "",
        trim_end    = "",
        fade_in     = False,
        fade_out    = True,
    )
    db.session.add(clip)
    db.session.flush()

    # Auto-add the clip to library's default playlist
    default_pl.clips.append(clip)

    db.session.commit()
    return jsonify({
        "ok":         True,
        "id":         song.id,
        "name":       song.orig_name,
        "clip_id":    clip.id,
        "library_id": library.id,
        "playlist_id": default_pl.id,
    })


# -----------------------------------------------------------------------------
# DELETE SONG
# -----------------------------------------------------------------------------
@bp.route("/<int:song_id>/delete", methods=["POST"])
@login_required
def delete_song(song_id):
    song = db.session.get(AudioFile, song_id)
    if not song or song.user_id != current_user.id:
        abort(404)
    delete_audio_files(current_user.id, song.filename)
    db.session.delete(song)
    db.session.commit()
    if request.headers.get("Accept", "").startswith("application/json") or \
       request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    return redirect(url_for("audio.index"))


# -----------------------------------------------------------------------------
# SCAN DURATIONS
# -----------------------------------------------------------------------------
@bp.route("/scan-durations", methods=["POST"])
@login_required
def scan_durations():
    from mutagen import File as MutagenFile
    fixed = 0
    songs = AudioFile.query.filter_by(user_id=current_user.id).all()
    for song in songs:
        if song.duration_s and song.duration_s > 0:
            continue
        path = audio_dir(current_user.id) / song.filename
        try:
            m = MutagenFile(str(path))
            if m and m.info and m.info.length:
                song.duration_s = float(m.info.length)
                fixed += 1
        except Exception:
            pass
    if fixed:
        db.session.commit()
    return jsonify({"fixed": fixed, "total": len(songs)})


# -----------------------------------------------------------------------------
# LIBRARY CRUD (was: song-folders)
# -----------------------------------------------------------------------------
@bp.route("/libraries", methods=["POST"])
@login_required
def create_library():
    """Create a new library. Auto-creates a default playlist with same name."""
    data = request.form if request.form else (request.json or {})
    name = (data.get("name") or "").strip()[:100]
    if not name:
        return jsonify({"error": "name required"}), 400

    library = Library(
        user_id    = current_user.id,
        name       = name,
        color      = data.get("color", "#2E3271"),
        sort_order = int(data.get("sort_order") or 0),
    )
    db.session.add(library)
    db.session.flush()

    default_pl = Playlist(
        user_id    = current_user.id,
        library_id = library.id,
        name       = name,
        color      = library.color,
        sort_order = 0,
        is_default = True,
    )
    db.session.add(default_pl)

    db.session.commit()
    if request.headers.get("Accept", "").startswith("application/json") or \
       request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "id": library.id,
                        "default_playlist_id": default_pl.id})
    return redirect(url_for("audio.index"))


@bp.route("/libraries/<int:library_id>", methods=["PUT", "POST"])
@login_required
def update_library(library_id):
    library = db.session.get(Library, library_id)
    if not library or library.user_id != current_user.id:
        abort(404)
    data = request.form if request.form else (request.json or {})

    if data.get("name"):
        library.name = data["name"].strip()[:100]
    if data.get("color"):
        library.color = data["color"]
    if "sort_order" in data:
        library.sort_order = int(data["sort_order"] or 0)

    # Rename the default playlist to match if it exists
    default_pl = Playlist.query.filter_by(
        library_id=library.id, is_default=True
    ).first()
    if default_pl:
        default_pl.name  = library.name
        default_pl.color = library.color

    db.session.commit()
    if request.headers.get("Accept", "").startswith("application/json") or \
       request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    return redirect(url_for("audio.index"))


@bp.route("/libraries/<int:library_id>", methods=["DELETE"])
@login_required
def delete_library(library_id):
    library = db.session.get(Library, library_id)
    if not library or library.user_id != current_user.id:
        abort(404)
    # Move songs in this library back to "Unsorted" (or None)
    for song in library.songs:
        song.library_id = None
    # Playlists get cascade-deleted via ORM relationship
    db.session.delete(library)
    db.session.commit()
    return jsonify({"ok": True})


# -----------------------------------------------------------------------------
# SONG -> LIBRARY ASSIGNMENT
# -----------------------------------------------------------------------------
@bp.route("/<int:song_id>/library", methods=["POST"])
@login_required
def assign_song_library(song_id):
    song = db.session.get(AudioFile, song_id)
    if not song or song.user_id != current_user.id:
        abort(404)
    library_id = request.form.get("library_id")
    if library_id:
        library = db.session.get(Library, int(library_id))
        if not library or library.user_id != current_user.id:
            return jsonify({"error": "invalid library"}), 400
        song.library_id = library.id
    else:
        song.library_id = None
    db.session.commit()
    if request.headers.get("Accept", "").startswith("application/json") or \
       request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "library_id": song.library_id})
    return redirect(url_for("audio.index"))


# -----------------------------------------------------------------------------
# STREAM (redirects to presigned R2 URL for HTML5 audio playback)
# -----------------------------------------------------------------------------
@bp.route("/stream/<int:song_id>")
@login_required
def stream_song(song_id):
    from app.services import r2 as r2svc
    song = db.session.get(AudioFile, song_id)
    if not song or song.user_id != current_user.id:
        abort(404)
    key = r2svc.audio_key(song.user_id, song.filename)
    url = r2svc.presigned_url(key, expires=600)
    return redirect(url)


# -----------------------------------------------------------------------------
# CLIPS
# -----------------------------------------------------------------------------
@bp.route("/clips")
@login_required
def clips():
    songs     = AudioFile.query.filter_by(user_id=current_user.id).all()
    all_clips = AudioClip.query\
                  .join(AudioFile, AudioClip.song_id == AudioFile.id)\
                  .filter(AudioFile.user_id == current_user.id)\
                  .order_by(AudioClip.name).all()
    libraries = Library.query.filter_by(user_id=current_user.id)\
                  .order_by(Library.sort_order, Library.name).all()
    return render_template("audio/clips.html",
                           songs=songs, clips=all_clips, libraries=libraries)


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

    if not data.get("name"):
        base = song.orig_name.rsplit(".", 1)[0] if "." in song.orig_name else song.orig_name
        num  = len(song.clips.all()) + 1
        name = f"{base} - {num}"
    else:
        name = data["name"].strip()[:100]

    user_clip_num = len(song.clips.all())
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
    db.session.flush()

    # If the song is in a library, auto-add this clip to the library's default playlist
    if song.library_id:
        default_pl = Playlist.query.filter_by(
            library_id=song.library_id, is_default=True
        ).first()
        if default_pl:
            default_pl.clips.append(clip)

    db.session.commit()
    return jsonify(clip.to_dict())


@bp.route("/clips/<int:clip_id>", methods=["PUT"])
@login_required
def update_clip(clip_id):
    clip = db.session.get(AudioClip, clip_id)
    if not clip or clip.song.user_id != current_user.id:
        abort(404)
    data = request.json or {}
    for field in ("name", "description", "trim_start", "trim_end"):
        if field in data:
            clip.__setattr__(field, data[field])
    for field in ("fade_in", "fade_out", "normalize"):
        if field in data:
            clip.__setattr__(field, bool(data[field]))
    db.session.commit()
    return jsonify(clip.to_dict())


@bp.route("/clips/<int:clip_id>/duplicate", methods=["POST"])
@login_required
def duplicate_clip(clip_id):
    """Duplicate an existing clip with the next available numeric name."""
    source = db.session.get(AudioClip, clip_id)
    if not source or source.song.user_id != current_user.id:
        abort(404)

    song = source.song
    # Next numeric name: base = song orig_name minus extension, next num = clips count + 1
    base = song.orig_name.rsplit(".", 1)[0] if "." in song.orig_name else song.orig_name
    num  = song.clips.count() + 1
    name = f"{base} - {num}"

    # User clip number for auto-description: current count is position of the first user clip,
    # so if there are already N clips (position 1 = Full Song), duplicate becomes position N+1 = "Clip N"
    user_clip_num = song.clips.count()
    default_desc = f"Clip {user_clip_num}" if user_clip_num > 0 else "Full Song"

    clip = AudioClip(
        song_id     = source.song_id,
        name        = name,
        description = default_desc,
        trim_start  = source.trim_start,
        trim_end    = source.trim_end,
        fade_in     = source.fade_in,
        fade_out    = source.fade_out,
        normalize   = source.normalize,
    )
    db.session.add(clip)
    db.session.flush()

    # Auto-add to song's library's default playlist (matches upload behavior)
    if song.library_id:
        default_pl = Playlist.query.filter_by(
            library_id=song.library_id, is_default=True
        ).first()
        if default_pl:
            default_pl.clips.append(clip)

    db.session.commit()
    return jsonify(clip.to_dict())


@bp.route("/clips/<int:clip_id>", methods=["DELETE"])
@login_required
def delete_clip(clip_id):
    clip = db.session.get(AudioClip, clip_id)
    if not clip or clip.song.user_id != current_user.id:
        abort(404)
    db.session.delete(clip)
    db.session.commit()
    return jsonify({"ok": True})


# -----------------------------------------------------------------------------
# LABELS (existing system; untouched by Session A migration)
# -----------------------------------------------------------------------------
@bp.route("/playlists")
@login_required
def playlists_page():
    """Renamed from labels_page. Underlying AudioLabel model unchanged for now -
    render pipeline (projects.py) still calls them 'labels' internally."""
    labels = AudioLabel.query.filter_by(user_id=current_user.id)\
                             .order_by(AudioLabel.sort_order, AudioLabel.name).all()
    songs  = AudioFile.query.filter_by(user_id=current_user.id)\
                            .order_by(AudioFile.orig_name).all()
    all_clips = AudioClip.query\
                  .join(AudioFile, AudioClip.song_id == AudioFile.id)\
                  .filter(AudioFile.user_id == current_user.id)\
                  .order_by(AudioClip.name).all()
    return render_template("audio/playlists.html",
                           playlists=labels, songs=songs, all_clips=all_clips)


@bp.route("/labels", methods=["POST"])
@login_required
def create_label():
    data = request.json or {}
    name = (data.get("name") or "").strip()[:50]
    if not name:
        return jsonify({"error": "name required"}), 400
    label = AudioLabel(
        user_id    = current_user.id,
        name       = name,
        color      = data.get("color", "#B4761F"),
        sort_order = int(data.get("sort_order") or 0),
    )
    db.session.add(label)
    db.session.commit()
    return jsonify({"ok": True, "id": label.id})


@bp.route("/labels/<int:label_id>", methods=["PUT"])
@login_required
def update_label(label_id):
    label = db.session.get(AudioLabel, label_id)
    if not label or label.user_id != current_user.id:
        abort(404)
    data = request.json or {}
    if data.get("name"):  label.name  = data["name"].strip()[:50]
    if data.get("color"): label.color = data["color"]
    if "sort_order" in data: label.sort_order = int(data["sort_order"] or 0)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/labels/<int:label_id>", methods=["DELETE"])
@login_required
def delete_label(label_id):
    label = db.session.get(AudioLabel, label_id)
    if not label or label.user_id != current_user.id:
        abort(404)
    db.session.delete(label)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/labels/<int:label_id>/clips", methods=["POST"])
@login_required
def add_clip_to_label(label_id):
    label = db.session.get(AudioLabel, label_id)
    if not label or label.user_id != current_user.id:
        abort(404)
    data = request.json or {}
    clip_id = data.get("clip_id")
    clip = db.session.get(AudioClip, clip_id)
    if not clip or clip.song.user_id != current_user.id:
        abort(404)
    if clip not in label.clips:
        label.clips.append(clip)
        db.session.commit()
    return jsonify({"ok": True})


@bp.route("/labels/<int:label_id>/import/<int:source_label_id>", methods=["POST"])
@login_required
def import_from_label(label_id, source_label_id):
    label  = db.session.get(AudioLabel, label_id)
    source = db.session.get(AudioLabel, source_label_id)
    if not label or not source: abort(404)
    if label.user_id != current_user.id or source.user_id != current_user.id:
        abort(404)
    added = 0
    for clip in source.clips:
        if clip not in label.clips:
            label.clips.append(clip)
            added += 1
    db.session.commit()
    return jsonify({"ok": True, "added": added})


# -----------------------------------------------------------------------------
# CLIP EDITOR PAGE
# -----------------------------------------------------------------------------
@bp.route("/<int:song_id>/clip-editor")
@login_required
def clip_editor(song_id):
    song = db.session.get(AudioFile, song_id)
    if not song or song.user_id != current_user.id:
        abort(404)
    return render_template("audio/clip_editor.html", song=song)