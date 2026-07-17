from datetime import datetime, timezone
from app.extensions import db, login_manager
from flask_login import UserMixin


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id              = db.Column(db.Integer,     primary_key=True)
    email           = db.Column(db.String(255), unique=True, nullable=False, index=True)
    first_name      = db.Column(db.String(100), nullable=False)
    last_name       = db.Column(db.String(100), nullable=False)
    phone           = db.Column(db.String(30),  unique=True, nullable=True)
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

    # Suspension / deactivation audit
    suspended_at        = db.Column(db.DateTime)
    suspended_by        = db.Column(db.Integer, db.ForeignKey("users.id"))
    suspension_reason   = db.Column(db.String(500))
    deactivated_at      = db.Column(db.DateTime)
    deactivated_by      = db.Column(db.Integer, db.ForeignKey("users.id"))
    # Storage + verification tracking
    storage_used_bytes  = db.Column(db.BigInteger, default=0)
    last_login_ip       = db.Column(db.String(45))
    last_login_user_agent = db.Column(db.String(500))
    email_verified_at   = db.Column(db.DateTime)
    phone_verified_at   = db.Column(db.DateTime)
    avatar_url          = db.Column(db.String(500))
    admin_notes         = db.Column(db.Text)
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
    events      = db.relationship("Event",     back_populates="user",
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
        event_bytes   = sum(p.storage_bytes for p in self.events)
        audio_bytes   = sum(a.file_size    for a in self.audio_files)
        return event_bytes + audio_bytes

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


    # ── Derived properties ────────────────────────────────────────
    @property
    def status(self):
        """Derived from is_enabled + suspended_at + is_active."""
        if not self.is_enabled:
            return "pending"
        if self.suspended_at:
            return "suspended"
        if not self.is_active:
            return "deactivated"
        return "active"

    @property
    def status_label(self):
        return {
            "pending":     "Pending approval",
            "active":      "Active",
            "suspended":   "Suspended",
            "deactivated": "Deactivated",
        }.get(self.status, self.status)

    @property
    def avatar_color(self):
        """Deterministic color per user id, drawn from the Rajasthani palette."""
        palette = ["#2E3271", "#1F225A", "#B4761F", "#2F7D4F", "#B23A48", "#4A5170"]
        return palette[(self.id or 0) % len(palette)]

    @property
    def initials(self):
        f = (self.first_name or "?")[:1]
        l = (self.last_name  or "?")[:1]
        return (f + l).upper()

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def phone_display(self):
        """Masked phone for admin lists. Returns None if no phone."""
        if not self.phone:
            return None
        p = self.phone.strip()
        if len(p) < 6:
            return p
        return p[:5] + "***" + p[-3:]

    @property
    def storage_pct(self):
        used  = self.storage_used_bytes or 0
        quota = self.quota_bytes or 1
        return min(100, int(round(100 * used / quota)))

    @property
    def storage_used_display(self):
        return _fmt_bytes(self.storage_used_bytes or 0)

    @property
    def quota_display(self):
        return _fmt_bytes(self.quota_bytes or 0)


def _fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


class RegistrationRequest(db.Model):
    """Pending registration — awaiting admin approval."""
    __tablename__ = "registration_requests"

    id              = db.Column(db.Integer,     primary_key=True)
    first_name      = db.Column(db.String(100), nullable=False)
    last_name       = db.Column(db.String(100), nullable=False)
    email           = db.Column(db.String(255), nullable=False)
    phone           = db.Column(db.String(30),  nullable=True)
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
