"""
Migration script: pCloud → Cloudflare R2
Migrates all photos, thumbnails, processed frames, audio, and output files.

Run once from Windows:
  cd P:\slideshow\slideshow_studio
  .\venv\Scripts\python.exe migrate_to_r2.py
"""
import os
import sys
import boto3
from botocore.config import Config
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
CF_ACCOUNT_ID        = os.environ["CF_ACCOUNT_ID"]
CF_R2_ACCESS_KEY_ID  = os.environ["CF_R2_ACCESS_KEY_ID"]
CF_R2_SECRET_ACCESS_KEY = os.environ["CF_R2_SECRET_ACCESS_KEY"]
CF_R2_ENDPOINT       = os.environ.get("CF_R2_ENDPOINT",
    f"https://{CF_ACCOUNT_ID}.r2.cloudflarestorage.com")
CF_R2_BUCKET         = os.environ.get("CF_R2_BUCKET", "slideshow-studio")

# pCloud local base path (Windows)
STORAGE_BASE = Path(os.environ.get("STORAGE_BASE", r"P:\slideshow"))

s3 = boto3.client("s3",
    endpoint_url          = CF_R2_ENDPOINT,
    aws_access_key_id     = CF_R2_ACCESS_KEY_ID,
    aws_secret_access_key = CF_R2_SECRET_ACCESS_KEY,
    config                = Config(signature_version="s3v4"),
    region_name           = "auto",
)

uploaded  = 0
skipped   = 0
errors    = 0


def r2_exists(key):
    try:
        s3.head_object(Bucket=CF_R2_BUCKET, Key=key)
        return True
    except Exception:
        return False


def upload(local_path, r2_key, content_type="image/jpeg"):
    global uploaded, skipped, errors
    if r2_exists(r2_key):
        print(f"  SKIP  {r2_key}")
        skipped += 1
        return
    try:
        s3.upload_file(str(local_path), CF_R2_BUCKET, r2_key,
                       ExtraArgs={"ContentType": content_type})
        print(f"  UP    {r2_key}")
        uploaded += 1
    except Exception as e:
        print(f"  ERROR {r2_key}: {e}")
        errors += 1


def mime(path):
    ext = Path(path).suffix.lower()
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "mp3": "audio/mpeg", "m4a": "audio/mp4", "wav": "audio/wav",
            "ogg": "audio/ogg", "aac": "audio/aac",
            "mp4": "video/mp4"}.get(ext.lstrip("."), "application/octet-stream")


users_dir = STORAGE_BASE / "users"
if not users_dir.exists():
    print(f"ERROR: Storage base not found: {users_dir}")
    sys.exit(1)

print(f"Migrating from: {users_dir}")
print(f"Migrating to:   {CF_R2_BUCKET}")
print()

# ── Migrate per user ──────────────────────────────────────────────────────────
for user_dir in sorted(users_dir.iterdir()):
    if not user_dir.is_dir():
        continue
    user_id = user_dir.name
    if not user_id.isdigit():
        continue
    print(f"\n=== User {user_id} ===")

    # ── Audio clips ───────────────────────────────────────────────────────────
    audio_orig = user_dir / "audio" / "original"
    if audio_orig.exists():
        print(f"\n  Audio originals ({user_id}):")
        for f in sorted(audio_orig.iterdir()):
            if f.is_file():
                upload(f, f"users/{user_id}/audio/{f.name}", mime(f))

    # ── Projects ──────────────────────────────────────────────────────────────
    projects_dir = user_dir / "projects"
    if not projects_dir.exists():
        continue

    for proj_dir in sorted(projects_dir.iterdir()):
        if not proj_dir.is_dir():
            continue
        project_id = proj_dir.name
        print(f"\n  Project: {project_id}")

        # Photos (originals)
        photos_dir = proj_dir / "photos"
        if photos_dir.exists():
            print(f"    Photos:")
            for f in sorted(photos_dir.iterdir()):
                if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    upload(f, f"users/{user_id}/projects/{project_id}/photos/{f.name}", mime(f))

        # Thumbnails
        thumbs_dir = proj_dir / "thumbs"
        if thumbs_dir.exists():
            print(f"    Thumbnails:")
            for f in sorted(thumbs_dir.iterdir()):
                if f.is_file():
                    upload(f, f"users/{user_id}/projects/{project_id}/thumbs/{f.name}", mime(f))

        # Processed frames
        processed_base = proj_dir / "processed"
        if processed_base.exists():
            for ver_dir in sorted(processed_base.iterdir()):
                if not ver_dir.is_dir():
                    continue
                ver = ver_dir.name
                print(f"    Processed/{ver}:")
                for f in sorted(ver_dir.iterdir()):
                    if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg"):
                        upload(f, f"users/{user_id}/projects/{project_id}/processed/{ver}/{f.name}", mime(f))
                # Thumbs subfolder
                thumb_sub = ver_dir / "thumbs"
                if thumb_sub.exists():
                    for f in sorted(thumb_sub.iterdir()):
                        if f.is_file():
                            upload(f, f"users/{user_id}/projects/{project_id}/processed/{ver}/thumbs/{f.name}", mime(f))

        # Output MP4s
        output_dir = proj_dir / "output"
        if output_dir.exists():
            print(f"    Output videos:")
            for f in sorted(output_dir.iterdir()):
                if f.is_file() and f.suffix.lower() == ".mp4":
                    upload(f, f"users/{user_id}/projects/{project_id}/output/{f.name}", "video/mp4")

print(f"\n{'='*50}")
print(f"Migration complete!")
print(f"  Uploaded: {uploaded}")
print(f"  Skipped:  {skipped} (already in R2)")
print(f"  Errors:   {errors}")
