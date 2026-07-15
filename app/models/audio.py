"""
Audio-related models.

- Library:   top-level container for songs (was: SongFolder)
- AudioFile: uploaded audio file - lives in exactly one Library
- AudioClip: slice of a song (name, start, end)
- Playlist:  collection of clips. Every Library gets a default Playlist.
             User can create additional playlists that reference clips.
- PlaylistClip: many-to-many join between Playlist and AudioClip
- AudioLabel: legacy label system (untouched)
"""
from app.extensions import db
from datetime import datetime


class Library(db.Model):
    __tablename__ = "libraries"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name       = db.Column(db.String(100), nullable=False)
    color      = db.Column(db.String(10))
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user     = db.relationship("User", backref=db.backref("libraries", lazy="dynamic"))
    songs    = db.relationship("AudioFile", backref="library", lazy="dynamic",
                               foreign_keys="AudioFile.library_id")
    playlists = db.relationship("Playlist", backref="library", lazy="dynamic",
                                foreign_keys="Playlist.library_id",
                                cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":         self.id,
            "name":       self.name,
            "color":      self.color,
            "sort_order": self.sort_order,
            "song_count": self.songs.count() if hasattr(self.songs, "count") else 0,
        }


class AudioFile(db.Model):
    __tablename__ = "audio_files"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename    = db.Column(db.String(255), nullable=False)
    orig_name   = db.Column(db.String(255))
    file_size   = db.Column(db.BigInteger)
    duration_s  = db.Column(db.Float)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    library_id  = db.Column(db.Integer, db.ForeignKey("libraries.id"))

    user  = db.relationship("User", backref=db.backref("audio_files", lazy="dynamic"))
    clips = db.relationship("AudioClip", backref="song", lazy="dynamic",
                            cascade="all, delete-orphan")


class AudioClip(db.Model):
    __tablename__ = "audio_clips"

    id          = db.Column(db.Integer, primary_key=True)
    song_id     = db.Column(db.Integer, db.ForeignKey("audio_files.id"), nullable=False)
    name        = db.Column(db.String(100), nullable=False)
    trim_start  = db.Column(db.String(20))
    trim_end    = db.Column(db.String(20))
    description = db.Column(db.String(200))
    fade_in     = db.Column(db.Boolean, default=False)
    fade_out    = db.Column(db.Boolean, default=True)
    normalize   = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    labels = db.relationship("AudioLabel",
                             secondary="audio_clip_labels",
                             back_populates="clips")

    def to_dict(self):
        return {
            "id":          self.id,
            "song_id":     self.song_id,
            "name":        self.name,
            "trim_start":  self.trim_start,
            "trim_end":    self.trim_end,
            "description": self.description,
            "fade_in":     self.fade_in,
            "fade_out":    self.fade_out,
            "normalize":   self.normalize,
        }


class Playlist(db.Model):
    __tablename__ = "playlists"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    library_id = db.Column(db.Integer, db.ForeignKey("libraries.id"))
    name       = db.Column(db.String(100), nullable=False)
    color      = db.Column(db.String(10))
    sort_order = db.Column(db.Integer, default=0)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user  = db.relationship("User", backref=db.backref("playlists", lazy="dynamic"))
    clips = db.relationship("AudioClip",
                            secondary="playlist_clips",
                            order_by="PlaylistClip.sort_order",
                            backref="playlists")

    def to_dict(self):
        return {
            "id":         self.id,
            "library_id": self.library_id,
            "name":       self.name,
            "color":      self.color,
            "sort_order": self.sort_order,
            "is_default": bool(self.is_default),
            "clip_count": len(self.clips),
        }


class PlaylistClip(db.Model):
    __tablename__ = "playlist_clips"

    playlist_id = db.Column(db.Integer, db.ForeignKey("playlists.id"), primary_key=True)
    clip_id     = db.Column(db.Integer, db.ForeignKey("audio_clips.id"), primary_key=True)
    sort_order  = db.Column(db.Integer, nullable=False, default=0)
    added_at    = db.Column(db.DateTime, default=datetime.utcnow)


class AudioLabel(db.Model):
    __tablename__ = "audio_labels"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name       = db.Column(db.String(50), nullable=False)
    color      = db.Column(db.String(10))
    sort_order = db.Column(db.Integer, default=0)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user   = db.relationship("User", backref=db.backref("audio_labels", lazy="dynamic"))
    clips  = db.relationship("AudioClip",
                             secondary="audio_clip_labels",
                             back_populates="labels")

    def clips_by_key(self):
        """Return dict keyed by clip id for O(1) lookup."""
        return {c.id: c for c in self.clips}


class AudioClipLabel(db.Model):
    __tablename__ = "audio_clip_labels"

    clip_id  = db.Column(db.Integer, db.ForeignKey("audio_clips.id"), primary_key=True)
    label_id = db.Column(db.Integer, db.ForeignKey("audio_labels.id"), primary_key=True)


# Backwards-compat alias so any lingering code that still says SongFolder
# doesn't fail immediately. Remove once we're sure nothing external uses it.
SongFolder = Library