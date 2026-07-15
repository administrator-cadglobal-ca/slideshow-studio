import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent


class Config:
    # ── Core ──────────────────────────────────────────────────────────────────
    SECRET_KEY          = os.environ.get("SECRET_KEY", "dev-key-change-in-prod")
    APP_URL             = os.environ.get("APP_URL", "http://localhost:5000")

    # ── Database ──────────────────────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI         = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR}/slideshow_studio.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS  = False

    # ── Storage ───────────────────────────────────────────────────────────────
    STORAGE_ROOT        = Path(os.environ.get("STORAGE_ROOT", BASE_DIR / "storage"))
    TEMP_ROOT           = Path(os.environ.get("TEMP_ROOT",
                              "D:/Temp/slideshow_render" if os.name == "nt"
                              else "/tmp/slideshow"))
    SLIDESHOW_MAKER_PATH = Path(os.environ.get(
                              "SLIDESHOW_MAKER_PATH",
                              BASE_DIR / "engine" / "slideshow_maker.py"))
    MAX_UPLOAD_BYTES    = int(os.environ.get("MAX_UPLOAD_MB", 50)) * 1024 * 1024
    DEFAULT_QUOTA_BYTES = int(os.environ.get("DEFAULT_QUOTA_GB", 20)) * 1024 ** 3

    ALLOWED_IMAGE_EXTS  = {".jpg", ".jpeg", ".png", ".heic", ".bmp", ".tiff", ".webp"}
    ALLOWED_AUDIO_EXTS  = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma", ".opus"}

    # ── Celery / Redis ────────────────────────────────────────────────────────
    CELERY_BROKER_URL   = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # ── Google OAuth ──────────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI  = os.environ.get(
        "GOOGLE_REDIRECT_URI", "http://localhost:5000/auth/google/callback"
    )
    GOOGLE_SCOPES = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/photoslibrary.appendonly",
    ]

    # ── Email ─────────────────────────────────────────────────────────────────
    MAIL_SERVER         = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT           = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS        = os.environ.get("MAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
    MAIL_USE_SSL        = os.environ.get("MAIL_USE_SSL", "False").lower() in ("true", "1", "yes")
    MAIL_USERNAME       = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD       = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "")

    # ── Render engine ─────────────────────────────────────────────────────────

    FFMPEG_PATH          = os.environ.get("FFMPEG_PATH", "ffmpeg")
    # Cloudflare (Calgary Dhamaka slideshow sharing)
    CF_ACCOUNT_ID        = os.environ.get("CF_ACCOUNT_ID", "")
    CF_API_TOKEN         = os.environ.get("CF_API_TOKEN", "")
    CF_R2_BUCKET         = os.environ.get("CF_R2_BUCKET", "slideshow-studio")
    CF_D1_ID             = os.environ.get("CF_D1_ID", "")
    CF_R2_ACCESS_KEY_ID  = os.environ.get("CF_R2_ACCESS_KEY_ID", "")
    CF_R2_SECRET_ACCESS_KEY = os.environ.get("CF_R2_SECRET_ACCESS_KEY", "")
    CF_R2_ENDPOINT       = os.environ.get("CF_R2_ENDPOINT", "")
    TEMP_DIR             = os.environ.get("TEMP_DIR", "/tmp")
    MAX_CONCURRENT_RENDERS = int(os.environ.get("MAX_CONCURRENT_RENDERS", 1))

    # ── Auto-cleanup ──────────────────────────────────────────────────────────
    SOURCE_CLEANUP_HOURS  = int(os.environ.get("SOURCE_CLEANUP_HOURS", 48))

    # ── SMS / Twilio ──────────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID  = os.environ.get("TWILIO_ACCOUNT_SID",  "")
    TWILIO_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN",   "")
    TWILIO_FROM_NUMBER  = os.environ.get("TWILIO_FROM_NUMBER",  "")

    # ── Admin ─────────────────────────────────────────────────────────────────
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
    ADMIN_PHONE = os.environ.get("ADMIN_PHONE", "+10000000001")


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    DEBUG = False
    # Session lifetime � user must re-authenticate every 24 hours
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    REMEMBER_COOKIE_DURATION  = timedelta(hours=24)
    SESSION_COOKIE_SECURE   = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


config = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "default":     DevelopmentConfig,
}
