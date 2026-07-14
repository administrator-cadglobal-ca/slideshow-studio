from datetime import datetime, timezone
from app.extensions import db


# ── Many-to-many: clip ↔ label ────────────────────────────────────────────────
audio_clip_labels = db.Table(
    "audio_clip_labels",
    db.Column("clip_id",  db.Integer, db.ForeignKey("audio_clips.id"),  primary_key=True),
    db.Column("label_id", db.Integer, db.ForeignKey("audio_labels.id"), primary_key=True),
)


class SongFolder(db.Model):
    """Organisational folder for songs in the Song Library."""
    __tablename__ = "song_folders"

    id         = db.Column(db.Integer,     primary_key=True)
    user_id    = db.Column(db.Integer,     db.ForeignKey("users.id"), nullable=False)
    name       = db.Column(db.String(100), nullable=False)
    color      = db.Column(db.String(10),  default="#1e3a52")
    sort_order = db.Column(db.Integer,     default=0)
    created_at = db.Column(db.DateTime, default=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc))

    user  = db.relationship("User")
    songs = db.relationship("AudioFile", back_populates="song_folder")

    @property
    def song_count(self):
        return len(self.songs)

    @property
    def clip_count(self):
        return sum(s.clip_count for s in self.songs)

    def __repr__(self):
        return f"<SongFolder {self.name}>"


class AudioFile(db.Model):
    """Uploaded original song — source file only, never trimmed."""
    __tablename__ = "audio_files"

    id          = db.Column(db.Integer,     primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename    = db.Column(db.String(255), nullable=False)
    orig_name   = db.Column(db.String(255))
    file_size   = db.Column(db.BigInteger,  default=0)
    duration_s  = db.Column(db.Float)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    song_folder_id = db.Column(db.Integer, db.ForeignKey("song_folders.id"), nullable=True)
    song_folder    = db.relationship("SongFolder", back_populates="songs")
    user           = db.relationship("User", back_populates="audio_files")
    clips = db.relationship("AudioClip", back_populates="song",
                            cascade="all, delete-orphan",
                            order_by="AudioClip.name")

    @property
    def duration_display(self) -> str:
        if not self.duration_s:
            return "--:--"
        m, s = divmod(int(self.duration_s), 60)
        return f"{m}:{s:02d}"

    @property
    def clip_count(self) -> int:
        return len(self.clips)

    def __repr__(self):
        return f"<AudioFile {self.orig_name}>"


class AudioClip(db.Model):
    """
    A named playback window on a song.
    trim_start / trim_end blank = full song.
    No file generated — ffmpeg trims at render time.
    """
    __tablename__ = "audio_clips"

    id          = db.Column(db.Integer,  primary_key=True)
    song_id     = db.Column(db.Integer,  db.ForeignKey("audio_files.id"), nullable=False)
    name        = db.Column(db.String(100), nullable=False, default="Full song")
    trim_start  = db.Column(db.String(20), default="")
    trim_end    = db.Column(db.String(20), default="")
    description = db.Column(db.String(200), default="")   # optional description
    fade_in     = db.Column(db.Boolean, default=False)
    fade_out    = db.Column(db.Boolean, default=True)
    normalize   = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    song   = db.relationship("AudioFile", back_populates="clips")
    labels = db.relationship("AudioLabel", secondary="audio_clip_labels",
                             back_populates="clips")

    @property
    def is_full_song(self) -> bool:
        return not self.trim_start and not self.trim_end

    @property
    def start_s(self) -> float:
        return _parse_time_s(self.trim_start)

    @property
    def end_s(self):
        return _parse_time_s(self.trim_end) if self.trim_end else None

    @property
    def effective_duration_s(self):
        if not self.song.duration_s:
            return None
        end = self.end_s or self.song.duration_s
        return max(0, end - self.start_s)

    @property
    def duration_display(self) -> str:
        d = self.effective_duration_s
        if not d:
            return self.song.duration_display
        m, s = divmod(int(d), 60)
        return f"{m}:{s:02d}"

    @property
    def trim_label(self) -> str:
        if self.is_full_song:
            return "Full song"
        start = self.trim_start or "0:00"
        end   = self.trim_end   or "end"
        return f"{start} → {end}"

    @property
    def display_name(self) -> str:
        """Song name + clip name for display in project picker."""
        if self.name == "Full song":
            return self.song.orig_name
        return f"{self.song.orig_name} — {self.name}"

    def to_dict(self) -> dict:
        return {
            "id":              self.id,
            "song_id":         self.song_id,
            "song_name":       self.song.orig_name,
            "name":            self.name,
            "display_name":    self.display_name,
            "trim_start":      self.trim_start,
            "trim_end":        self.trim_end,
            "trim_label":      self.trim_label,
            "duration_display":self.duration_display,
            "is_full_song":    self.is_full_song,
            "description":     self.description or "",
            "fade_in":         self.fade_in,
            "fade_out":        self.fade_out,
            "normalize":       self.normalize,
            "label_ids":       [l.id for l in self.labels],
        }

    def __repr__(self):
        return f"<AudioClip {self.display_name}>"


class AudioLabel(db.Model):
    """
    A named group of clips (full songs or trimmed).
    Auto-created when a project is created.
    Can also be created manually for reusable collections.
    """
    __tablename__ = "audio_labels"

    id          = db.Column(db.Integer,  primary_key=True)
    user_id     = db.Column(db.Integer,  db.ForeignKey("users.id"),    nullable=False)
    project_id  = db.Column(db.Integer,  db.ForeignKey("projects.id"), nullable=True)
    name        = db.Column(db.String(100), nullable=False)
    color       = db.Column(db.String(10),  default="#1e3a52")
    sort_order  = db.Column(db.Integer,     default=0)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user    = db.relationship("User")
    project = db.relationship("Project", back_populates="audio_label", foreign_keys=[project_id])
    clips   = db.relationship("AudioClip", secondary="audio_clip_labels",
                              back_populates="labels",
                              order_by="AudioClip.song_id, AudioClip.name")

    @property
    def clip_count(self) -> int:
        return len(self.clips)

    @property
    def is_project_label(self) -> bool:
        return self.project_id is not None

    @property
    def total_duration_s(self):
        total = 0
        for clip in self.clips:
            d = clip.effective_duration_s
            if d:
                total += d
        return total or None

    @property
    def total_duration_display(self) -> str:
        d = self.total_duration_s
        if not d:
            return "--:--"
        m, s = divmod(int(d), 60)
        return f"{m}:{s:02d}"

    def __repr__(self):
        return f"<AudioLabel {self.name}>"


def _parse_time_s(t: str) -> float:
    try:
        parts = str(t).strip().split(":")
        if len(parts) == 2: return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        return float(t)
    except Exception:
        return 0.0
