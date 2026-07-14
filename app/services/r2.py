"""
Cloudflare R2 storage service — S3-compatible via boto3.
All media (photos, audio, processed frames, renders) stored in R2.
Hetzner server handles only app code, SQLite DB, and temp processing.
"""
from __future__ import annotations
import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from flask import current_app
from pathlib import Path
import threading

_client_lock = threading.Lock()
_s3_client   = None


def get_client():
    """Return a cached boto3 S3 client for R2."""
    global _s3_client
    with _client_lock:
        if _s3_client is None:
            cfg = current_app.config
            _s3_client = boto3.client(
                "s3",
                endpoint_url          = cfg.get("CF_R2_ENDPOINT",
                    f"https://{cfg.get('CF_ACCOUNT_ID')}.r2.cloudflarestorage.com"),
                aws_access_key_id     = cfg.get("CF_R2_ACCESS_KEY_ID"),
                aws_secret_access_key = cfg.get("CF_R2_SECRET_ACCESS_KEY"),
                config                = Config(signature_version="s3v4"),
                region_name           = "auto",
            )
    return _s3_client


def bucket():
    return current_app.config.get("CF_R2_BUCKET", "slideshow-studio")


# ── Key helpers ───────────────────────────────────────────────────────────────

def photo_key(user_id, project_id, filename):
    return f"users/{user_id}/projects/{project_id}/photos/{filename}"

def thumb_key(user_id, project_id, filename):
    return f"users/{user_id}/projects/{project_id}/thumbs/{filename}"

def processed_key(user_id, project_id, version, filename):
    return f"users/{user_id}/projects/{project_id}/processed/{version}/{filename}"

def processed_thumb_key(user_id, project_id, version, filename):
    return f"users/{user_id}/projects/{project_id}/processed/{version}/thumbs/{filename}"

def audio_key(user_id, filename):
    return f"users/{user_id}/audio/{filename}"

def output_key(user_id, project_id, filename):
    return f"users/{user_id}/projects/{project_id}/output/{filename}"


# ── Upload ────────────────────────────────────────────────────────────────────

def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream"):
    """Upload raw bytes to R2."""
    get_client().put_object(
        Bucket      = bucket(),
        Key         = key,
        Body        = data,
        ContentType = content_type,
    )

def upload_file(key: str, filepath: str | Path, content_type: str = "application/octet-stream"):
    """Upload a local file to R2."""
    get_client().upload_file(
        str(filepath),
        bucket(),
        key,
        ExtraArgs={"ContentType": content_type},
    )

def upload_fileobj(key: str, fileobj, content_type: str = "application/octet-stream"):
    """Upload a file-like object to R2."""
    get_client().upload_fileobj(
        fileobj,
        bucket(),
        key,
        ExtraArgs={"ContentType": content_type},
    )


# ── Download ──────────────────────────────────────────────────────────────────

def download_bytes(key: str) -> bytes:
    """Download object from R2 as bytes."""
    resp = get_client().get_object(Bucket=bucket(), Key=key)
    return resp["Body"].read()

def download_file(key: str, filepath: str | Path):
    """Download R2 object to local file."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    get_client().download_file(bucket(), key, str(filepath))


# ── Listing ───────────────────────────────────────────────────────────────────

def list_keys(prefix: str) -> list[str]:
    """List all keys under a prefix."""
    s3  = get_client()
    bkt = bucket()
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bkt, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys

def list_filenames(prefix: str) -> list[str]:
    """List just the filenames (no prefix) under a prefix."""
    prefix = prefix.rstrip("/") + "/"
    return [k[len(prefix):] for k in list_keys(prefix)
            if not k[len(prefix):].startswith("/") and k[len(prefix):]  ]

def exists(key: str) -> bool:
    """Check if a key exists in R2."""
    try:
        get_client().head_object(Bucket=bucket(), Key=key)
        return True
    except ClientError:
        return False

def delete(key: str):
    """Delete a key from R2."""
    get_client().delete_object(Bucket=bucket(), Key=key)

def delete_prefix(prefix: str):
    """Delete all keys under a prefix."""
    keys = list_keys(prefix)
    if not keys:
        return
    s3 = get_client()
    # Delete in batches of 1000
    for i in range(0, len(keys), 1000):
        s3.delete_objects(
            Bucket=bucket(),
            Delete={"Objects": [{"Key": k} for k in keys[i:i+1000]]}
        )


# ── Presigned URLs ────────────────────────────────────────────────────────────

def presigned_url(key: str, expires: int = 3600) -> str:
    """Generate a presigned URL for temporary public access."""
    return get_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket(), "Key": key},
        ExpiresIn=expires,
    )


# ── Temp dir for processing ───────────────────────────────────────────────────

def get_temp_dir(job_id: str) -> Path:
    """Get a temp directory for processing jobs."""
    tmp = Path(current_app.config.get("TEMP_DIR", "/tmp")) / f"slideshow_{job_id}"
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp

def cleanup_temp_dir(job_id: str):
    """Remove temp directory after processing."""
    import shutil
    tmp = Path(current_app.config.get("TEMP_DIR", "/tmp")) / f"slideshow_{job_id}"
    if tmp.exists():
        shutil.rmtree(str(tmp), ignore_errors=True)
