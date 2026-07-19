from flask       import Blueprint, render_template, request, jsonify, abort, redirect, url_for
from flask_login import login_required, current_user

from app.extensions      import db
from app.models.audio    import AudioFile, AudioClip, Playlist, Library, Playlist, PlaylistClip
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
                  .order_by(AudioFile.sort_order, AudioFile.id).all()
    labels    = db.session.query(Playlist)\
                  .filter_by(user_id=current_user.id)\
                  .order_by(Playlist.sort_order, Playlist.name).all()
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

    # Check if it's an archive - if so, extract audio files inside
    orig_filename = (f.filename or "").lower()
    ARCHIVE_EXTS = (".zip", ".7z", ".rar", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz")
    if any(orig_filename.endswith(ext) for ext in ARCHIVE_EXTS):
        return _handle_archive_upload(f, request.form.get("library_id"), orig_filename)

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

    # Create the song. sort_order = current max + 1 so new songs land at end.
    max_sort = db.session.query(db.func.coalesce(db.func.max(AudioFile.sort_order), 0))\
                 .filter_by(user_id=current_user.id).scalar() or 0
    song = AudioFile(
        user_id     = current_user.id,
        filename    = result["filename"],
        orig_name   = result["orig_name"],
        file_size   = result["file_size"],
        duration_s  = result.get("duration_s"),
        library_id  = library.id,
        sort_order  = max_sort + 1,
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
    # Enforce empty-first rule
    song_count = AudioFile.query.filter_by(library_id=library.id).count()
    if song_count > 0:
        return jsonify({
            "error": f"This library still contains {song_count} song(s). Please move or delete them first."
        }), 400
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
                  .order_by(AudioClip.sort_order, AudioClip.id).all()
    libraries = Library.query.filter_by(user_id=current_user.id)\
                  .order_by(Library.sort_order, Library.name).all()
    # Playlists (Playlist rows under Path B naming) for the "Add to playlist" picker
    playlists = Playlist.query.filter_by(user_id=current_user.id)\
                                .order_by(Playlist.sort_order, Playlist.name).all()
    return render_template("audio/clips.html",
                           songs=songs, clips=all_clips,
                           libraries=libraries, playlists=playlists)


@bp.route("/songs/batch-move", methods=["POST"])
@login_required
def batch_move_songs():
    """Reassign multiple songs to a library.
    Body: {"song_ids": [1,2,3], "library_id": 5 or null}"""
    data = request.json or {}
    song_ids = data.get("song_ids", [])
    library_id = data.get("library_id")
    if library_id is not None:
        lib = db.session.get(Library, int(library_id))
        if not lib or lib.user_id != current_user.id:
            return jsonify({"error": "invalid library"}), 400
        library_id = lib.id
    songs = AudioFile.query.filter_by(user_id=current_user.id)\
                           .filter(AudioFile.id.in_(song_ids)).all()
    for s in songs:
        s.library_id = library_id
    db.session.commit()
    return jsonify({"ok": True, "moved": len(songs), "library_id": library_id})


@bp.route("/songs/reorder", methods=["POST"])
@login_required
def reorder_songs():
    """Update sort_order for songs.
    Body: {"song_ids": [3, 1, 2]} means song id 3 first, then 1, then 2."""
    data = request.json or {}
    song_ids = data.get("song_ids", [])
    songs = AudioFile.query.filter_by(user_id=current_user.id)\
                           .filter(AudioFile.id.in_(song_ids)).all()
    songs_by_id = {s.id: s for s in songs}
    for idx, sid in enumerate(song_ids):
        s = songs_by_id.get(int(sid))
        if s:
            s.sort_order = idx + 1
    db.session.commit()
    return jsonify({"ok": True, "reordered": len(songs)})


@bp.route("/clips/reorder", methods=["POST"])
@login_required
def reorder_clips():
    """Update sort_order for clips.
    Body: {"clip_ids": [5, 2, 7]} means clip id 5 first, then 2, then 7."""
    data = request.json or {}
    clip_ids = data.get("clip_ids", [])
    clips = AudioClip.query\
              .join(AudioFile, AudioClip.song_id == AudioFile.id)\
              .filter(AudioFile.user_id == current_user.id)\
              .filter(AudioClip.id.in_(clip_ids)).all()
    clips_by_id = {c.id: c for c in clips}
    for idx, cid in enumerate(clip_ids):
        c = clips_by_id.get(int(cid))
        if c:
            c.sort_order = idx + 1
    db.session.commit()
    return jsonify({"ok": True, "reordered": len(clips)})


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

    max_clip_sort = db.session.query(db.func.coalesce(db.func.max(AudioClip.sort_order), 0))\
                      .join(AudioFile, AudioClip.song_id == AudioFile.id)\
                      .filter(AudioFile.user_id == current_user.id).scalar() or 0
    clip = AudioClip(
        song_id     = song_id,
        name        = name,
        description = data.get("description", "").strip() or default_desc,
        trim_start  = data.get("trim_start", ""),
        trim_end    = data.get("trim_end", ""),
        fade_in     = data.get("fade_in", False),
        fade_out    = data.get("fade_out", True),
        normalize   = data.get("normalize", False),
        sort_order  = max_clip_sort + 1,
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

    max_clip_sort = db.session.query(db.func.coalesce(db.func.max(AudioClip.sort_order), 0))\
                      .join(AudioFile, AudioClip.song_id == AudioFile.id)\
                      .filter(AudioFile.user_id == current_user.id).scalar() or 0
    clip = AudioClip(
        song_id     = source.song_id,
        name        = name,
        description = default_desc,
        trim_start  = source.trim_start,
        trim_end    = source.trim_end,
        fade_in     = source.fade_in,
        fade_out    = source.fade_out,
        normalize   = source.normalize,
        sort_order  = max_clip_sort + 1,
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
    """Renamed from labels_page. Underlying Playlist model unchanged for now -
    render pipeline (events.py) still calls them 'labels' internally."""
    labels = Playlist.query.filter_by(user_id=current_user.id)\
                             .order_by(Playlist.sort_order, Playlist.name).all()
    songs  = AudioFile.query.filter_by(user_id=current_user.id)\
                            .order_by(AudioFile.orig_name).all()
    all_clips = AudioClip.query\
                  .join(AudioFile, AudioClip.song_id == AudioFile.id)\
                  .filter(AudioFile.user_id == current_user.id)\
                  .order_by(AudioClip.sort_order, AudioClip.id).all()
    return render_template("audio/playlists.html",
                           playlists=labels, songs=songs, all_clips=all_clips)


@bp.route("/labels", methods=["POST"])
@login_required
def create_label():
    data = request.json or {}
    name = (data.get("name") or "").strip()[:50]
    if not name:
        return jsonify({"error": "name required"}), 400
    label = Playlist(
        user_id    = current_user.id,
        name       = name,
        color      = data.get("color", "#B4761F"),
        sort_order = int(data.get("sort_order") or 0),
    )
    db.session.add(label)
    db.session.commit()
    return jsonify({"ok": True, "id": label.id})


@bp.route("/labels/<int:playlist_id>", methods=["PUT"])
@login_required
def update_label(playlist_id):
    label = db.session.get(Playlist, playlist_id)
    if not label or label.user_id != current_user.id:
        abort(404)
    data = request.json or {}
    if data.get("name"):  label.name  = data["name"].strip()[:50]
    if data.get("color"): label.color = data["color"]
    if "sort_order" in data: label.sort_order = int(data["sort_order"] or 0)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/labels/<int:playlist_id>", methods=["DELETE"])
@login_required
def delete_label(playlist_id):
    label = db.session.get(Playlist, playlist_id)
    if not label or label.user_id != current_user.id:
        abort(404)
    # Enforce empty-first rule
    clip_count = len(label.clips)
    if clip_count > 0:
        return jsonify({
            "error": f"This playlist still contains {clip_count} clip(s). Please remove them first."
        }), 400
    db.session.delete(label)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/labels/<int:playlist_id>/clips/batch", methods=["POST"])
@login_required
def batch_add_clips_to_label(playlist_id):
    """Add multiple clips to a playlist (label) in one call.
    Body: {"clip_ids": [1, 2, 3]}"""
    label = db.session.get(Playlist, playlist_id)
    if not label or label.user_id != current_user.id:
        abort(404)
    data = request.json or {}
    clip_ids = data.get("clip_ids", [])
    added = 0
    for cid in clip_ids:
        clip = db.session.get(AudioClip, int(cid))
        if not clip or clip.song.user_id != current_user.id:
            continue
        if clip not in label.clips:
            label.clips.append(clip)
            added += 1
    db.session.commit()
    return jsonify({"ok": True, "added": added, "playlist_size": len(label.clips)})


@bp.route("/labels/<int:playlist_id>/clips/reorder", methods=["POST"])
@login_required
def reorder_playlist_clips(playlist_id):
    """Reorder clips within a playlist (label).
    Body: {"clip_ids": [3, 1, 2]} means clip 3 first, then 1, then 2."""
    label = db.session.get(Playlist, playlist_id)
    if not label or label.user_id != current_user.id:
        abort(404)
    data = request.json or {}
    clip_ids = data.get("clip_ids", [])
    # Update sort_order in the playlist_clips join table directly.
    from sqlalchemy import text
    for idx, cid in enumerate(clip_ids):
        db.session.execute(
            text("UPDATE playlist_clips SET sort_order = :so "
                 "WHERE playlist_id = :lid AND clip_id = :cid"),
            {"so": idx + 1, "lid": playlist_id, "cid": int(cid)}
        )
    db.session.commit()
    return jsonify({"ok": True, "reordered": len(clip_ids)})


@bp.route("/labels/<int:playlist_id>/clips/<int:clip_id>", methods=["DELETE"])
@login_required
def remove_clip_from_label(playlist_id, clip_id):
    """Remove a clip from a playlist (label). Clip itself is not deleted."""
    label = db.session.get(Playlist, playlist_id)
    if not label or label.user_id != current_user.id:
        abort(404)
    clip = db.session.get(AudioClip, clip_id)
    if not clip or clip.song.user_id != current_user.id:
        abort(404)
    if clip in label.clips:
        label.clips.remove(clip)
        db.session.commit()
    return jsonify({"ok": True})


@bp.route("/labels/<int:playlist_id>/clips", methods=["POST"])
@login_required
def add_clip_to_label(playlist_id):
    label = db.session.get(Playlist, playlist_id)
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


@bp.route("/labels/<int:playlist_id>/import/<int:source_playlist_id>", methods=["POST"])
@login_required
def import_from_label(playlist_id, source_playlist_id):
    label  = db.session.get(Playlist, playlist_id)
    source = db.session.get(Playlist, source_playlist_id)
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

def _extract_members(archive_file, filename):
    """Extract members from various archive formats. Returns list of (name, bytes) tuples."""
    import zipfile
    import tarfile
    import os as _os
    from io import BytesIO

    filename_l = filename.lower()
    data = archive_file.read()
    members = []

    if filename_l.endswith(".zip"):
        with zipfile.ZipFile(BytesIO(data)) as zf:
            for m in zf.namelist():
                if m.endswith("/") or "__MACOSX" in m or _os.path.basename(m).startswith("."):
                    continue
                with zf.open(m) as inner:
                    members.append((m, inner.read()))
    elif filename_l.endswith(".7z"):
        import py7zr
        with py7zr.SevenZipFile(BytesIO(data)) as zf:
            extracted = zf.readall()
            for name, bio in extracted.items():
                if name.endswith("/") or _os.path.basename(name).startswith("."):
                    continue
                members.append((name, bio.read()))
    elif filename_l.endswith(".rar"):
        import rarfile
        import tempfile
        # rarfile needs a real file
        with tempfile.NamedTemporaryFile(suffix=".rar", delete=False) as tf:
            tf.write(data)
            temp_path = tf.name
        try:
            with rarfile.RarFile(temp_path) as rf:
                for m in rf.namelist():
                    if m.endswith("/") or _os.path.basename(m).startswith("."):
                        continue
                    members.append((m, rf.read(m)))
        finally:
            _os.unlink(temp_path)
    elif any(filename_l.endswith(x) for x in (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz")):
        mode = "r:*"
        with tarfile.open(fileobj=BytesIO(data), mode=mode) as tf:
            for m in tf.getmembers():
                if not m.isfile() or _os.path.basename(m.name).startswith("."):
                    continue
                f = tf.extractfile(m)
                if f:
                    members.append((m.name, f.read()))

    return members


def _handle_archive_upload(archive_file, library_id, filename):
    """Extract audio files from any supported archive and upload each. Returns summary."""
    import os as _os
    from io import BytesIO
    from werkzeug.datastructures import FileStorage
    from flask import jsonify as _jsonify

    AUDIO_EXTS = {".mp3", ".m4a", ".mp4", ".wav", ".ogg", ".flac", ".aac", ".webm"}

    try:
        all_members = _extract_members(archive_file, filename)
    except Exception as e:
        return _jsonify({"error": f"Invalid or corrupted archive: {e}"}), 400

    uploaded_count = 0
    skipped = []
    errors = []

    # Resolve library
    library = None
    if library_id:
        library = db.session.get(Library, int(library_id))
        if not library or library.user_id != current_user.id:
            library = None
    if library is None:
        library = Library.query.filter_by(user_id=current_user.id, name="Unsorted").first()
        if library is None:
            library = Library(user_id=current_user.id, name="Unsorted", color="#8A90A8", sort_order=999)
            db.session.add(library)
            db.session.commit()

    default_playlist = db.session.query(Playlist).filter_by(library_id=library.id, is_default=True).first()
    if default_playlist is None:
        default_playlist = db.session.query(Playlist).filter_by(library_id=library.id).first()
    if default_playlist is None:
        default_playlist = Playlist(library_id=library.id, name=library.name, user_id=current_user.id, is_default=True, color=library.color)
        db.session.add(default_playlist)
        db.session.commit()

    for member, file_bytes in all_members:
        ext = _os.path.splitext(member)[1].lower()
        if ext not in AUDIO_EXTS:
            skipped.append(_os.path.basename(member))
            continue
        try:
            file_stream = BytesIO(file_bytes)
            safe_name = _os.path.basename(member)
            fs = FileStorage(stream=file_stream, filename=safe_name, content_type="audio/mpeg")
            result = save_uploaded_audio(fs, current_user.id)
            # Create song row
            # save_uploaded_audio already created AudioFile + AudioClip
            # We just need to attach the AudioClip to our default playlist
            audio_file_id = result.get("audio_file_id") or result.get("id")
            audio_clip_id = result.get("audio_clip_id") or result.get("clip_id")
            if audio_file_id:
                from app.models.audio import AudioFile
                af = db.session.get(AudioFile, audio_file_id)
                if af:
                    af.library_id = library.id
            if audio_clip_id:
                from app.models.audio import PlaylistClip
                # Get max sort_order
                existing_max = db.session.query(db.func.max(PlaylistClip.sort_order))\
                    .filter_by(playlist_id=default_playlist.id).scalar() or 0
                pc = PlaylistClip(
                    playlist_id = default_playlist.id,
                    clip_id     = audio_clip_id,
                    sort_order  = existing_max + 1,
                )
                db.session.add(pc)
            uploaded_count += 1
        except Exception as e:
            errors.append({"file": member, "error": str(e)[:100]})

    db.session.commit()
    return _jsonify({
        "ok": True,
        "uploaded": uploaded_count,
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "errors": errors[:5],
        "message": f"Uploaded {uploaded_count} audio file(s) from ZIP" + (f", skipped {len(skipped)} non-audio" if skipped else ""),
    })