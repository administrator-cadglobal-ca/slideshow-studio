"""
Storage service — all file paths rooted at STORAGE_ROOT.

Local dev:   STORAGE_ROOT=/home/user/slideshow_storage
Production:  STORAGE_ROOT=/pcloud/slideshow

Everything lives on pCloud in production:
    users/{id}/audio/original/        ← raw uploaded songs
    users/{id}/audio/clipped/         ← trimmed AudioClip_ versions
    users/{id}/events/{pid}/source/     ← uploaded photos (deleted post-render)
    users/{id}/events/{pid}/processed/  ← processed frame JPEGs (kept)
    users/{id}/events/{pid}/output/     ← final MP4s (kept)
    users/{id}/events/{pid}/logs/       ← render logs

Temp render working files (never on pCloud):
    TEMP_ROOT/render_{job_id}/            ← ffmpeg temp clips, deleted after concat
"""

from pathlib  import Path
from flask    import current_app
from PIL      import Image
import uuid, os, shutil


# ── Root helpers ───────────────────────────────────────────────────────────────

def storage_root() -> Path:
    return Path(current_app.config["STORAGE_ROOT"])

def temp_root() -> Path:
    """
    Temp working dir on LOCAL disk — NOT pCloud.
    Windows dev : D:/Temp/slideshow_render  (set TEMP_ROOT=P: is wrong — use local C:)
    Linux prod  : /tmp/slideshow
    Always local SSD, never the pCloud mount.
    """
    t = Path(current_app.config["TEMP_ROOT"])
    t.mkdir(parents=True, exist_ok=True)
    return t

def _d(path: Path) -> Path:
    """Create directory and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


# ── User directories ───────────────────────────────────────────────────────────

def user_dir(user_id: int) -> Path:
    return _d(storage_root() / "users" / str(user_id))

def audio_dir(user_id: int, sub: str = "original") -> Path:
    """sub = 'original' | 'clipped'"""
    return _d(user_dir(user_id) / "audio" / sub)

def project_dir(user_id: int, event_id: str) -> Path:
    return _d(user_dir(user_id) / "projects" / event_id)

def source_dir(user_id: int, event_id: str) -> Path:
    return _d(project_dir(user_id, event_id) / "source")

def thumb_dir(user_id: int, event_id: str) -> Path:
    return _d(project_dir(user_id, event_id) / "thumbs")

def processed_dir(user_id: int, event_id: str, version: str = "") -> Path:
    """
    Processed frame JPEGs — saved to pCloud, kept after render.
    version e.g. '1920x1080_normal', '1080x1920_smart', '1080x1920_stack'
    """
    base = project_dir(user_id, event_id) / "processed"
    if version:
        return _d(base / version)
    return _d(base)

def output_dir(user_id: int, event_id: str) -> Path:
    """Final MP4s — kept on pCloud permanently."""
    return _d(project_dir(user_id, event_id) / "output")

def log_dir(user_id: int, event_id: str) -> Path:
    return _d(project_dir(user_id, event_id) / "logs")

def render_temp_dir(job_id: str) -> Path:
    """
    Temporary working directory on LOCAL SSD during render.
    Contains ffmpeg temp clip files — deleted automatically after concat.
    Never written to pCloud.
    """
    return _d(temp_root() / f"render_{job_id}")


# ── Photo upload ───────────────────────────────────────────────────────────────

def save_uploaded_photo(file_storage, user_id: int, event_id: str) -> dict:
    """
    Save uploaded photo to pCloud source dir.
    Fixes EXIF rotation, generates thumbnail.
    Returns dict: filename, file_size, width, height, orientation, exif_date
    """
    ext      = Path(file_storage.filename).suffix.lower()
    filename = f"{uuid.uuid4()}{ext}"
    src_path = source_dir(user_id, event_id) / filename

    file_storage.save(str(src_path))
    file_size = src_path.stat().st_size

    width = height = None
    orientation = "landscape"
    meta = {}

    try:
        from PIL import ImageOps
        img = Image.open(src_path)

        # Extract full EXIF metadata including GPS
        from app.services.exif import extract_metadata, reverse_geocode
        meta = extract_metadata(src_path)

        # Fix EXIF rotation before saving
        img = ImageOps.exif_transpose(img)
        img.save(src_path)

        width, height = img.size
        if height > width:
            orientation = "portrait"
        elif width == height:
            orientation = "square"

        # Generate thumbnail (320px) for list/filmstrip
        thumb = img.copy()
        thumb.thumbnail((320, 320), Image.LANCZOS)
        thumb.save(str(thumb_dir(user_id, event_id) / f"thumb_{filename}"), quality=85)

        # Generate preview (1280px) for main stage display
        prev_img = img.copy()
        prev_img.thumbnail((1280, 1280), Image.LANCZOS)
        prev_dir = _d(project_dir(user_id, event_id) / "previews")
        prev_img.save(str(prev_dir / f"prev_{filename}"), quality=88)

        # Reverse geocode GPS if present (runs in background thread to avoid blocking)
        if meta.get("gps_lat") and meta.get("gps_lon"):
            try:
                import threading
                def _geocode_bg():
                    try:
                        from app.extensions import db
                        from app.models import Photo
                        # Geocode
                        geo = reverse_geocode(meta["gps_lat"], meta["gps_lon"])
                        # The photo hasn't been committed yet, so store in meta for caller
                        meta.update(geo)
                    except Exception:
                        pass
                # Run synchronously on upload (1-2 seconds, acceptable)
                geo = reverse_geocode(meta["gps_lat"], meta["gps_lon"])
                meta.update(geo)
            except Exception:
                pass

    except Exception:
        pass

    return {
        "filename":       filename,
        "orig_name":      file_storage.filename,
        "file_size":      file_size,
        "width":          width,
        "height":         height,
        "orientation":    orientation,
        # EXIF fields — all passed through to Photo model
        **{k: meta.get(k) for k in [
            "exif_date", "exif_date_str",
            "camera_make", "camera_model", "lens_model",
            "focal_length", "focal_length_35",
            "aperture", "shutter_speed", "iso",
            "flash", "exposure_mode", "white_balance", "metering_mode",
            "gps_lat", "gps_lon", "gps_alt", "gps_speed", "gps_direction",
            "gps_location", "gps_place", "gps_country",
            "color_space", "software",
        ]},
    }


# ── Audio upload ───────────────────────────────────────────────────────────────

def save_uploaded_audio(file_storage, user_id: int) -> dict:
    """
    Save uploaded audio file to pCloud audio/original dir.
    Returns dict: filename, orig_name, file_size, duration_s
    """
    orig_name = file_storage.filename
    ext       = Path(orig_name).suffix.lower()
    filename  = f"{uuid.uuid4()}{ext}"
    dest      = audio_dir(user_id, "original") / filename

    file_storage.save(str(dest))
    file_size  = dest.stat().st_size
    duration_s = None

    # Try mutagen first (fast, no ffmpeg needed)
    try:
        from mutagen import File as MutagenFile
        audio_info = MutagenFile(str(dest))
        if audio_info and audio_info.info:
            duration_s = round(audio_info.info.length, 2)
    except Exception:
        pass

    # Fallback to moviepy
    if not duration_s:
        try:
            from moviepy import AudioFileClip
            clip       = AudioFileClip(str(dest))
            duration_s = round(clip.duration, 2)
            clip.close()
        except Exception:
            pass

    # Last resort: ffprobe
    if not duration_s:
        try:
            import subprocess, json
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_format", str(dest)],
                capture_output=True, text=True, timeout=10
            )
            info = json.loads(result.stdout)
            duration_s = round(float(info["format"]["duration"]), 2)
        except Exception:
            pass

    return {
        "filename":   filename,
        "orig_name":  orig_name,
        "file_size":  file_size,
        "duration_s": duration_s,
    }


# ── Cleanup ────────────────────────────────────────────────────────────────────

def delete_source_photos(user_id: int, event_id: str):
    """
    Delete source photos and thumbnails after successful render.
    Processed frames and output MP4s are KEPT on pCloud.
    """
    for d in (source_dir(user_id, event_id),
              thumb_dir(user_id, event_id)):
        if d.exists():
            shutil.rmtree(d)

def delete_project_files(user_id: int, event_id: str):
    """Delete ALL project files (source, processed, output, logs)."""
    d = project_dir(user_id, event_id)
    if d.exists():
        shutil.rmtree(d)

def delete_audio_files(user_id: int, filename: str):
    """Remove audio file from R2 (and local pCloud if exists)."""
    # Delete from R2
    try:
        from app.services import r2 as R2
        R2.delete(R2.audio_key(user_id, filename))
    except Exception:
        pass
    # Delete from local pCloud (legacy)
    for sub in ("original", "clipped"):
        for name in (filename, f"AudioClip_{filename}"):
            f = audio_dir(user_id, sub) / name
            try:
                if f.exists():
                    f.unlink(missing_ok=True)
            except Exception:
                pass

def cleanup_render_temp(job_id: str):
    """Remove local temp dir after render completes."""
    d = render_temp_dir(job_id)
    if d.exists():
        shutil.rmtree(d)


# ── Storage usage ──────────────────────────────────────────────────────────────

def get_dir_size(path: Path) -> int:
    """Return total size in bytes of all files under path."""
    total = 0
    if path.exists():
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
    return total


# ── URL helpers ────────────────────────────────────────────────────────────────

def thumb_url(user_id: int, event_id: str, filename: str) -> str:
    """Flask route URL for serving a thumbnail."""
    return f"/api/v1/media/thumbs/{user_id}/{event_id}/thumb_{filename}"

def output_url(user_id: int, event_id: str, filename: str) -> str:
    """Flask route URL for downloading an output MP4."""
    return f"/api/v1/media/output/{user_id}/{event_id}/{filename}"

def processed_url(user_id: int, event_id: str, version: str, filename: str) -> str:
    """Flask route URL for viewing a processed frame JPEG."""
    return f"/api/v1/media/processed/{user_id}/{event_id}/{version}/{filename}"


# ── Caption rendering ──────────────────────────────────────────────────────────

def burn_caption(img: "Image.Image", note: str, style: dict, line2: str = "") -> "Image.Image":
    """
    Burn a two-line caption onto a PIL Image.
    Line 1 (note)  : user description — larger, bold
    Line 2 (line2) : auto metadata (date, location, camera) — smaller, dimmer

    style keys: position, size, color, background
    Returns the modified image.
    """
    if not note and not line2:
        return img

    try:
        from PIL import ImageDraw, ImageFont, ImageFilter
        import textwrap

        draw  = ImageDraw.Draw(img, "RGBA")
        W, H  = img.size

        # Font size
        sizes = {"small": max(18, H // 45), "medium": max(24, H // 32), "large": max(32, H // 22)}
        font_size = sizes.get(style.get("size", "medium"), H // 32)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            except Exception:
                font = ImageFont.load_default()

        # Wrap text
        max_chars = max(20, int(W / (font_size * 0.55)))
        lines     = textwrap.wrap(note.strip(), width=max_chars)
        line_h    = font_size + 6
        text_h    = line_h * len(lines)
        pad       = int(font_size * 0.8)

        # Background
        bg_type = style.get("background", "gradient")
        bar_h   = text_h + pad * 2
        pos     = style.get("position", "bottom")

        if "bottom" in pos:
            bar_y = H - bar_h
        else:
            bar_y = 0

        if bg_type == "gradient":
            for i in range(bar_h + 60):
                alpha = int(180 * (i / (bar_h + 60)))
                y_pos = bar_y - 60 + i
                if 0 <= y_pos < H:
                    draw.line([(0, y_pos), (W, y_pos)], fill=(0, 0, 0, alpha))
        elif bg_type == "solid":
            draw.rectangle([(0, bar_y), (W, H)], fill=(0, 0, 0, 160))

        # Text colour
        hex_c = style.get("color", "#ffffff").lstrip("#")
        r, g, b = int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)

        align = "left" if "left" in pos else ("right" if "right" in pos else "center")

        # Draw line 1 — auto metadata (smaller, dimmer, sits above the description)
        y_cursor = bar_y + pad
        if line2 and line2.strip():
            try:
                font2_size = max(12, font_size - 6)
                try:
                    font2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font2_size)
                except Exception:
                    font2 = font
                meta_text = line2.strip()[:120]
                bbox2     = draw.textbbox((0, 0), meta_text, font=font2)
                tw2       = bbox2[2] - bbox2[0]
                if align == "center":  tx2 = (W - tw2) // 2
                elif align == "right": tx2 = W - tw2 - pad
                else:                  tx2 = pad
                r2 = min(255, int(r * .65))
                g2 = min(255, int(g * .65))
                b2 = min(255, int(b * .65))
                draw.text((tx2+1, y_cursor+1), meta_text, font=font2, fill=(0, 0, 0, 140))
                draw.text((tx2,   y_cursor),   meta_text, font=font2, fill=(r2, g2, b2, 200))
                y_cursor += (font2_size + 4)
            except Exception:
                pass

        # Draw line 2 — user description (larger, bright, anchored at bottom)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw   = bbox[2] - bbox[0]
            if align == "center":  tx = (W - tw) // 2
            elif align == "right": tx = W - tw - pad
            else:                  tx = pad
            draw.text((tx+1, y_cursor+1), line, font=font, fill=(0, 0, 0, 160))
            draw.text((tx,   y_cursor),   line, font=font, fill=(r, g, b, 255))
            y_cursor += line_h

    except Exception:
        pass  # Never let caption failure break the render

    return img


# ── R2-aware functions ────────────────────────────────────────────────────────

def save_uploaded_photo_r2(file_storage, user_id: int, event_id: str) -> dict:
    """
    Save uploaded photo to R2.
    Fixes EXIF rotation, generates thumbnail, uploads both to R2.
    Returns dict with metadata.
    """
    from app.services import r2 as R2
    import io, uuid as _uuid
    from PIL import ImageOps

    ext      = Path(file_storage.filename).suffix.lower() or ".jpg"
    filename = f"{_uuid.uuid4()}{ext}"

    # Read file into memory
    raw = file_storage.read()
    file_size = len(raw)

    width = height = None
    orientation = "landscape"
    meta = {}

    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
        width, height = img.size
        if height > width:
            orientation = "portrait"
        elif width == height:
            orientation = "square"

        # Try EXIF extraction
        try:
            from app.services.exif import extract_metadata
            import tempfile as _tf, os as _os
            with _tf.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(raw); tmppath = tmp.name
            meta = extract_metadata(Path(tmppath))
            _os.unlink(tmppath)
        except Exception:
            pass

        # Save EXIF-corrected JPEG to bytes
        buf = io.BytesIO()
        fmt = "JPEG" if ext.lower() in (".jpg", ".jpeg") else "PNG"
        img.convert("RGB").save(buf, format="JPEG", quality=95)
        corrected = buf.getvalue()

        # Generate thumbnail 320px
        thumb = img.copy()
        thumb.thumbnail((320, 320), Image.LANCZOS)
        tbuf = io.BytesIO()
        thumb.convert("RGB").save(tbuf, format="JPEG", quality=85)
        thumb_bytes = tbuf.getvalue()

        # Upload original + thumbnail to R2
        R2.upload_bytes(R2.photo_key(user_id, event_id, filename),
                        corrected, "image/jpeg")
        R2.upload_bytes(R2.thumb_key(user_id, event_id, f"thumb_{filename}"),
                        thumb_bytes, "image/jpeg")
        print(f"[R2] Uploaded photo+thumb: {filename}")

        # GPS reverse geocode
        if meta.get("gps_lat") and meta.get("gps_lon"):
            try:
                from app.services.exif import reverse_geocode
                geo = reverse_geocode(meta["gps_lat"], meta["gps_lon"])
                meta.update(geo)
            except Exception:
                pass

    except Exception as e:
        print(f"[R2] Photo processing error: {e}, uploading raw")
        R2.upload_bytes(R2.photo_key(user_id, event_id, filename),
                        raw, "image/jpeg")
        # Generate thumbnail from raw
        try:
            thumb2 = Image.open(io.BytesIO(raw))
            thumb2.thumbnail((320, 320), Image.LANCZOS)
            tbuf2 = io.BytesIO()
            thumb2.convert("RGB").save(tbuf2, format="JPEG", quality=85)
            R2.upload_bytes(R2.thumb_key(user_id, event_id, f"thumb_{filename}"),
                            tbuf2.getvalue(), "image/jpeg")
        except Exception as e2:
            print(f"[R2] Thumbnail fallback error: {e2}")

    return {
        "filename":    filename,
        "orig_name":   file_storage.filename,
        "file_size":   file_size,
        "width":       width,
        "height":      height,
        "orientation": orientation,
        **meta,
    }


def get_photo_url_r2(user_id: int, event_id: str, filename: str,
                     thumb: bool = False, expires: int = 3600) -> str:
    """Get presigned URL for a photo from R2."""
    from app.services import r2 as R2
    key = R2.thumb_key(user_id, event_id, f"thumb_{filename}") if thumb           else R2.photo_key(user_id, event_id, filename)
    return R2.presigned_url(key, expires)


def get_processed_url_r2(user_id: int, event_id: str, version: str,
                          filename: str, thumb: bool = False,
                          expires: int = 3600) -> str:
    """Get presigned URL for a processed frame from R2."""
    from app.services import r2 as R2
    key = R2.processed_thumb_key(user_id, event_id, version, filename) if thumb           else R2.processed_key(user_id, event_id, version, filename)
    return R2.presigned_url(key, expires)


def list_processed_versions_r2(user_id: int, event_id: str) -> dict:
    """List all processed versions and their frames from R2."""
    from app.services import r2 as R2
    prefix = f"users/{user_id}/events/{event_id}/processed/"
    all_keys = R2.list_keys(prefix)

    versions = {}
    for key in all_keys:
        # Strip prefix: processed/{version}/{filename} or processed/{version}/thumbs/{filename}
        rel = key[len(prefix):]
        parts = rel.split("/")
        if len(parts) < 2:
            continue
        ver = parts[0]
        if parts[1] == "thumbs":
            continue  # skip thumbs
        fname = "/".join(parts[1:])
        if fname.endswith(".jpg") or fname.endswith(".jpeg"):
            if ver not in versions:
                versions[ver] = []
            versions[ver].append(fname)

    # Sort filenames within each version
    for ver in versions:
        versions[ver] = sorted(versions[ver])

    return versions


def save_uploaded_audio_r2(file_storage, user_id: int) -> dict:
    """
    Save uploaded audio file to R2.
    Returns dict: filename, orig_name, file_size, duration_s
    """
    from app.services import r2 as R2
    import io, uuid as _uuid, tempfile, os

    orig_name = file_storage.filename
    ext       = Path(orig_name).suffix.lower() or ".mp3"
    filename  = f"{_uuid.uuid4()}{ext}"
    raw       = file_storage.read()
    file_size = len(raw)
    duration_s = None

    # Get duration via temp file
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(raw); tmppath = tmp.name
        try:
            from mutagen import File as MutagenFile
            audio_info = MutagenFile(tmppath)
            if audio_info and audio_info.info:
                duration_s = round(audio_info.info.length, 2)
        except Exception:
            pass
        os.unlink(tmppath)
    except Exception:
        pass

    # Upload to R2
    ct = "audio/mpeg" if ext in (".mp3", ".m4a") else "audio/ogg"
    R2.upload_bytes(R2.audio_key(user_id, filename), raw, ct)

    return {
        "filename":   filename,
        "orig_name":  orig_name,
        "file_size":  file_size,
        "duration_s": duration_s,
    }
