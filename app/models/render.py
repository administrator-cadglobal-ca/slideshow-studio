from datetime import datetime, timezone
from app.extensions import db
import uuid


class RenderJob(db.Model):
    """One render run — may produce multiple output files (one per version)."""
    __tablename__ = "render_jobs"

    id          = db.Column(db.String(36), primary_key=True,
                            default=lambda: str(uuid.uuid4()))
    project_id  = db.Column(db.String(36), db.ForeignKey("projects.id"), nullable=False)
    mode        = db.Column(db.String(20), default="production")
    # dev | fast | production

    status      = db.Column(db.String(20), default="queued")
    # queued | running | complete | failed | cancelled

    celery_task_id  = db.Column(db.String(255))
    queue_position  = db.Column(db.Integer, default=0)

    # Dev mode settings (overrides project defaults when mode=dev)
    dev_images          = db.Column(db.Integer, default=20)
    dev_songs           = db.Column(db.Integer, default=4)
    dev_images_per_song = db.Column(db.Integer, default=5)

    # Timing
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    started_at      = db.Column(db.DateTime)
    completed_at    = db.Column(db.DateTime)

    # Progress (updated by Celery worker via Redis)
    current_version = db.Column(db.String(50))    # e.g. "hd"
    current_step    = db.Column(db.String(100))   # e.g. "Building clips 42/179"
    progress_pct    = db.Column(db.Float, default=0.0)
    log_text        = db.Column(db.Text, default="")
    error_msg       = db.Column(db.Text)

    # Relationships
    project     = db.relationship("Project",       back_populates="render_jobs")
    versions    = db.relationship("RenderVersion", back_populates="job",
                                  cascade="all, delete-orphan",
                                  order_by="RenderVersion.started_at")
    outputs     = db.relationship("RenderOutput",  back_populates="job",
                                  cascade="all, delete-orphan")

    @property
    def duration_s(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_active(self) -> bool:
        return self.status in ("queued", "running")

    @property
    def output_count(self) -> int:
        return len(self.outputs)

    def append_log(self, line: str):
        self.log_text = (self.log_text or "") + line + "\n"

    def __repr__(self):
        return f"<RenderJob {self.id[:8]} {self.status}>"


class RenderVersion(db.Model):
    """Progress tracking for one version within a RenderJob."""
    __tablename__ = "render_versions"

    id          = db.Column(db.Integer,    primary_key=True)
    job_id      = db.Column(db.String(36), db.ForeignKey("render_jobs.id"), nullable=False)
    version_key = db.Column(db.String(30))  # "hd" | "4k" | "phone_smart" etc.
    label       = db.Column(db.String(50))  # "HD 1080p"
    resolution  = db.Column(db.String(20))  # "1920x1080"

    status      = db.Column(db.String(20), default="waiting")
    progress_pct = db.Column(db.Float,     default=0.0)
    started_at  = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    error_msg   = db.Column(db.Text)

    job         = db.relationship("RenderJob", back_populates="versions")

    def __repr__(self):
        return f"<RenderVersion {self.version_key} {self.status}>"


class RenderOutput(db.Model):
    """A completed output file ready for download."""
    __tablename__ = "render_outputs"

    id              = db.Column(db.Integer,    primary_key=True)
    job_id          = db.Column(db.String(36), db.ForeignKey("render_jobs.id"), nullable=False)
    version_key     = db.Column(db.String(30))
    filename        = db.Column(db.String(255))
    file_size       = db.Column(db.BigInteger, default=0)
    duration_s      = db.Column(db.Float)
    resolution      = db.Column(db.String(20))
    created_at      = db.Column(db.DateTime,   default=lambda: datetime.now(timezone.utc))
    expires_at      = db.Column(db.DateTime)   # None = keep until user deletes

    # Upload status
    youtube_video_id    = db.Column(db.String(50))   # set after YouTube upload
    google_photos_url   = db.Column(db.Text)         # set after Photos upload

    job             = db.relationship("RenderJob", back_populates="outputs")

    @property
    def file_size_mb(self) -> float:
        return round(self.file_size / 1_048_576, 1)

    def __repr__(self):
        return f"<RenderOutput {self.filename}>"
