from datetime import datetime, timezone
from app.extensions import db, login_manager
from flask_login import UserMixin


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id              = db.Column(db.Integer,     primary_key=True)
    email           = db.Column(db.String(255), unique=True, nullable=False, index=True)
    first_name      = db.Column(db.String(100), nullable=False)
    last_name       = db.Column(db.String(100), nullable=False)
    phone           = db.Column(db.String(30),  unique=True, nullable=False)
    # Username = phone number (E.164 format: +14031234567)

    role            = db.Column(db.String(20),  default="user")   # "admin" | "user"
    is_enabled      = db.Column(db.Boolean,     default=False)    # admin must enable
    is_active       = db.Column(db.Boolean,     default=True)     # admin can suspend

    # Registration metadata
    discount_code   = db.Column(db.String(50))
    signup_message  = db.Column(db.Text)        # message from user to admin at signup
    approved_by     = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at     = db.Column(db.DateTime)

    # Storage quota (bytes)
    quota_bytes     = db.Column(db.BigInteger, default=20 * 1024 ** 3)  # 20 GB

    # Notification preference
    notify_email    = db.Column(db.String(255))

    # Google OAuth tokens
    google_access_token  = db.Column(db.Text)
    google_refresh_token = db.Column(db.Text)
    google_token_expiry  = db.Column(db.DateTime)
    google_email         = db.Column(db.String(255))

    # Preferences
    pref_transition  = db.Column(db.String(20), default="fade")
    pref_fps         = db.Column(db.Integer,    default=24)
    pref_title_bg    = db.Column(db.String(10), default="#0d1b2a")
    pref_title_color = db.Column(db.String(10), default="#ffffff")

    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login  = db.Column(db.DateTime)

    # Relationships
    projects    = db.relationship("Project",   back_populates="user",
                                  cascade="all, delete-orphan")
    audio_files = db.relationship("AudioFile", back_populates="user",
                                  cascade="all, delete-orphan")
    otp_codes   = db.relationship("OTPCode",   back_populates="user",
                                  cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def storage_used(self) -> int:
        project_bytes = sum(p.storage_bytes for p in self.projects)
        audio_bytes   = sum(a.file_size    for a in self.audio_files)
        return project_bytes + audio_bytes

    @property
    def storage_pct(self) -> float:
        if self.quota_bytes == 0:
            return 0.0
        return min(100.0, self.storage_used / self.quota_bytes * 100)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def google_connected(self) -> bool:
        return bool(self.google_refresh_token)

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f"<User {self.email}>"


class RegistrationRequest(db.Model):
    """Pending registration — awaiting admin approval."""
    __tablename__ = "registration_requests"

    id              = db.Column(db.Integer,     primary_key=True)
    first_name      = db.Column(db.String(100), nullable=False)
    last_name       = db.Column(db.String(100), nullable=False)
    email           = db.Column(db.String(255), nullable=False)
    phone           = db.Column(db.String(30),  nullable=False)
    discount_code   = db.Column(db.String(50))
    message         = db.Column(db.Text)        # message to admin

    status          = db.Column(db.String(20), default="pending")
    # pending | approved | rejected

    reviewed_by     = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at     = db.Column(db.DateTime)
    review_note     = db.Column(db.Text)        # admin note on rejection
    created_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # set when approved and User record created

    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"<RegistrationRequest {self.email} {self.status}>"


class OTPCode(db.Model):
    """8-character alphanumeric OTP sent by SMS for login."""
    __tablename__ = "otp_codes"

    id          = db.Column(db.Integer,    primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    code        = db.Column(db.String(8),  nullable=False)   # UPPERCASE + DIGITS
    created_at  = db.Column(db.DateTime,
                            default=lambda: datetime.now(timezone.utc))
    expires_at  = db.Column(db.DateTime, nullable=False)
    used_at     = db.Column(db.DateTime)        # set when code is consumed
    attempts    = db.Column(db.Integer, default=0)  # failed attempts counter

    user        = db.relationship("User", back_populates="otp_codes")

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at.replace(tzinfo=timezone.utc)

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        return not self.is_used and not self.is_expired and self.attempts < 5

    def __repr__(self):
        return f"<OTPCode user={self.user_id} {'used' if self.is_used else 'valid'}>"


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))
