from datetime import datetime, timezone
from app.extensions import db
import uuid


class Event(db.Model):
    __tablename__ = "events"

    id              = db.Column(db.String(36),  primary_key=True,
                                default=lambda: str(uuid.uuid4()))
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name            = db.Column(db.String(255), nullable=False)
    slug            = db.Column(db.String(255))

    # ── Slideshow settings ────────────────────────────────────────────────────
    title_text      = db.Column(db.String(255), default="")
    title_subtitle  = db.Column(db.String(255), default="")
    title_duration  = db.Column(db.Float,       default=5.0)
    title_bg        = db.Column(db.String(10),  default="#0d1b2a")
    title_color     = db.Column(db.String(10),  default="#ffffff")

    end_text        = db.Column(db.String(255), default="Thank You for Watching")
    end_duration    = db.Column(db.Float,       default=4.0)
    end_bg          = db.Column(db.String(10),  default="#0d1b2a")
    end_color       = db.Column(db.String(10),  default="#ffffff")

    image_order     = db.Column(db.String(20),  default="sequential")
    image_duration  = db.Column(db.Float,       default=3.0)
    image_fit       = db.Column(db.String(20),  default="cover")
    stitch_portraits= db.Column(db.Boolean,     default=True)

    transition      = db.Column(db.String(20),  default="fade")
    fade_duration   = db.Column(db.Float,       default=1.0)
    fps             = db.Column(db.Integer,     default=24)

    auto_timing          = db.Column(db.Boolean, default=True)
    complete_last_song   = db.Column(db.Boolean, default=True)
    max_hold_duration    = db.Column(db.Float,   default=5.0)
    loop_audio           = db.Column(db.Boolean, default=True)
    audio_order          = db.Column(db.String(20), default="sequential")

    # ── Render versions ───────────────────────────────────────────────────────
    render_versions      = db.Column(db.String(255), default="hd,4k,phone_smart,phone_stack")

    # ── Caption settings ──────────────────────────────────────────────────────
    caption_style        = db.Column(db.Text)         # JSON: position, size, color, bg, burn
    caption_line2        = db.Column(db.String(60),   default="date_location")

    # ── Processed images ──────────────────────────────────────────────────────
    save_processed_images = db.Column(db.Boolean, default=False)
    save_images_confirm   = db.Column(db.Boolean, default=False)

    # ── State ─────────────────────────────────────────────────────────────────
    status          = db.Column(db.String(20), default="draft")

    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                                onupdate=lambda: datetime.now(timezone.utc))

    # ── Relationships ─────────────────────────────────────────────────────────
    user            = db.relationship("User", back_populates="events")
    photos          = db.relationship("Photo", back_populates="event",
                                      cascade="all, delete-orphan",
                                      order_by="Photo.sort_order")
    render_jobs     = db.relationship("RenderJob", back_populates="event",
                                      cascade="all, delete-orphan",
                                      order_by="RenderJob.created_at.desc()")
    audio_label     = db.relationship("AudioLabel", back_populates="event",
                                      foreign_keys="AudioLabel.event_id",
                                      uselist=False)
    selected_songs  = db.relationship("AudioFile",
                                      secondary="event_songs",
                                      order_by="event_songs.c.sort_order")

    @property
    def photo_count(self) -> int:
        return len([p for p in self.photos if not p.skipped])

    @property
    def storage_bytes(self) -> int:
        return sum(p.file_size or 0 for p in self.photos)

    @property
    def render_versions_list(self) -> list:
        return [v.strip() for v in (self.render_versions or "").split(",") if v.strip()]

    @property
    def latest_job(self):
        return self.render_jobs[0] if self.render_jobs else None

    @property
    def caption_style_parsed(self) -> dict:
        import json
        try:
            return json.loads(self.caption_style) if self.caption_style else {}
        except Exception:
            return {}

    def __repr__(self):
        return f"<Event {self.name}>"


# ── Join table: event ↔ audio files ────────────────────────────────────────
event_songs = db.Table(
    "event_songs",
    db.Column("event_id",    db.String(36), db.ForeignKey("events.id"),    primary_key=True),
    db.Column("audio_file_id", db.Integer,    db.ForeignKey("audio_files.id"), primary_key=True),
    db.Column("sort_order",    db.Integer,    default=0),
    db.Column("use_clipped",   db.Boolean,    default=True),
)


class ShareToken(db.Model):
    """Public share links and collaborator invites for events."""
    __tablename__ = "share_tokens"

    id             = db.Column(db.Integer, primary_key=True)
    token          = db.Column(db.String(64), unique=True, nullable=False, index=True)
    event_id       = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    created_by     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    share_type     = db.Column(db.String(16), default="public")
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    role           = db.Column(db.String(16), default="viewer")
    label_ids      = db.Column(db.Text, nullable=True)
    version        = db.Column(db.String(32), nullable=True)
    expires_at     = db.Column(db.DateTime, nullable=True)
    created_at     = db.Column(db.DateTime, default=db.func.now())
    last_used_at   = db.Column(db.DateTime, nullable=True)
    use_count      = db.Column(db.Integer, default=0)
    # Local-only fields (not sent to Cloudflare)
    description    = db.Column(db.String(200), nullable=True)   # e.g. "Family group"
    plain_password = db.Column(db.String(100), nullable=True)   # stored locally for owner reference
    versions_list  = db.Column(db.Text, nullable=True)          # JSON list of uploaded versions

    event = db.relationship("Event", foreign_keys=[event_id],
                              backref=db.backref("share_tokens", lazy="dynamic"))

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        from datetime import datetime
        return datetime.utcnow() > self.expires_at

    @property
    def public_url(self):
        return f"/s/{self.token}"
