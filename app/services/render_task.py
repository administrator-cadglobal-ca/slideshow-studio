"""
Celery task that runs slideshow_maker.py for a RenderJob.
Progress is written to the RenderJob record in the DB and
streamed to the browser via the /api/v1/renders/<job_id>/progress endpoint.
"""
from app.extensions  import celery_app, db
from app.models      import RenderJob, RenderVersion, RenderOutput, Event
from app.services.storage import source_dir, audio_dir, output_dir, log_dir
from datetime        import datetime, timezone
from pathlib         import Path
import subprocess, sys, os, json


@celery_app.task(bind=True, name="app.services.render_task.run_render")
def run_render(self, job_id: str):
    job = db.session.get(RenderJob, job_id)
    if not job:
        return

    event = job.event
    user_id = event.user_id

    job.status     = "running"
    job.started_at = datetime.now(timezone.utc)
    job.append_log(f"[{_ts()}] Render started  mode={job.mode}\n")
    db.session.commit()

    try:
        _run(job, event, user_id)
        job.status       = "complete"
        job.completed_at = datetime.now(timezone.utc)
        job.progress_pct = 100.0
        job.append_log(f"[{_ts()}] All versions complete.\n")

        # Update event status
        event.status = "complete"
        db.session.commit()

        # Send notification email
        _notify(job, event)

    except Exception as exc:
        job.status    = "failed"
        job.error_msg = str(exc)
        job.append_log(f"[{_ts()}] ERROR: {exc}\n")
        db.session.commit()
        raise


def _run(job: RenderJob, event: Event, user_id: int):
    """Build the slideshow_maker.py command and run it."""
    from flask import current_app

    maker_path = current_app.config["SLIDESHOW_MAKER_PATH"]
    src_dir    = source_dir(user_id, event.id)
    aud_dir    = audio_dir(user_id, "clipped")
    out_dir    = output_dir(user_id, event.id)
    log_path   = log_dir(user_id, event.id) / f"{job.id[:8]}.txt"

    # Output file path — version suffix added by slideshow_maker.py
    out_file = out_dir / f"{event.slug}.mp4"

    versions = ",".join(event.render_versions_list)

    cmd = [
        sys.executable, str(maker_path),
        "--images",          str(src_dir),
        "--music",           str(aud_dir),
        "--output",          str(out_file),
        "--render-versions", versions,
        "--duration",        str(event.image_duration),
        "--fps",             str(event.fps),
        "--fade-duration",   str(event.fade_duration),
        "--transition",      event.transition,
        "--image-fit",       event.image_fit,
        "--title-text",      event.title_text or "",
        "--title-subtitle",  event.title_subtitle or "",
        "--title-duration",  str(event.title_duration),
        "--title-bg",        event.title_bg,
        "--title-color",     event.title_color,
        "--end-text",        event.end_text or "",
        "--end-duration",    str(event.end_duration),
        "--end-bg",          event.end_bg,
        "--end-color",       event.end_color,
        "--max-hold-duration", str(event.max_hold_duration),
        "--audio-order",     event.audio_order,
        "--image-order",     event.image_order,
    ]

    if event.auto_timing:
        cmd.append("--auto-timing")
    if event.complete_last_song:
        cmd.append("--complete-last-song")
    if event.loop_audio:
        cmd.append("--loop-audio")
    if event.stitch_portraits:
        cmd.append("--stitch-portraits")
    if event.save_processed_images:
        cmd.append("--save-images")
    if event.save_images_confirm:
        cmd.append("--save-images-confirm")

    if job.mode == "dev":
        cmd += [
            "--dev-mode",
            "--dev-images",          str(job.dev_images),
            "--dev-songs",           str(job.dev_songs),
            "--dev-images-per-song", str(job.dev_images_per_song),
        ]

    # Run slideshow_maker.py and stream its output to the job log
    job.append_log(f"[{_ts()}] Running: {' '.join(cmd[:5])} ...\n")
    db.session.commit()

    with open(log_path, "w", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in proc.stdout:
            log_file.write(line)
            log_file.flush()
            job.append_log(line)
            _parse_progress(job, line)
            db.session.commit()

        proc.wait()

    if proc.returncode != 0:
        raise RuntimeError(f"slideshow_maker.py exited with code {proc.returncode}")

    # Register output files
    _register_outputs(job, event, out_dir)


def _parse_progress(job: RenderJob, line: str):
    """Extract progress info from slideshow_maker.py stdout lines."""
    line = line.strip()
    if "Rendering" in line and "/" in line:
        parts = line.split("/")
        try:
            current = int(parts[0].split("[")[-1])
            total   = int(parts[1].split("]")[0])
            job.progress_pct = round(current / total * 100, 1)
        except (ValueError, IndexError):
            pass
    if "mode=" in line:
        for part in line.split():
            if "mode=" in part:
                job.current_version = part.split("mode=")[-1]
    if "images written" in line.lower():
        job.current_step = line.strip()


def _register_outputs(job: RenderJob, event: Event, out_dir: Path):
    """Scan output folder and register RenderOutput records."""
    from app.models import RenderOutput

    VERSION_MAP = {
        "HD_1080p":       ("hd",          "1920x1080"),
        "2K_1440p":       ("2k",          "2560x1440"),
        "4K_2160p":       ("4k",          "3840x2160"),
        "8K_4320p":       ("8k",          "7680x4320"),
        "Phone_Smart":    ("phone_smart", "1080x1920"),
        "Phone_Stack":    ("phone_stack", "1080x1920"),
        "Phone_Split":    ("phone_split", "1080x1920"),
        "Phone_Bars":     ("phone_bars",  "1080x1920"),
        "Phone_Portrait": ("phone_only",  "1080x1920"),
        "SD_720p":        ("sd",          "1280x720"),
    }

    for mp4 in sorted(out_dir.glob("*.mp4")):
        version_key = "unknown"
        resolution  = ""
        for suffix, (vk, res) in VERSION_MAP.items():
            if suffix in mp4.name:
                version_key = vk
                resolution  = res
                break

        existing = db.session.query(RenderOutput)\
                     .filter_by(job_id=job.id, filename=mp4.name).first()
        if existing:
            continue

        ro = RenderOutput(
            job_id      = job.id,
            version_key = version_key,
            filename    = mp4.name,
            file_size   = mp4.stat().st_size,
            resolution  = resolution,
        )
        db.session.add(ro)

    db.session.commit()


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _notify(job: RenderJob, event: Event):
    """Send completion email if configured."""
    try:
        from flask_mail import Message
        from app.extensions import mail
        from flask import current_app, render_template_string

        user = event.user
        email = user.notify_email or user.email
        if not email or not current_app.config.get("MAIL_USERNAME"):
            return

        msg = Message(
            subject=f"Render complete — {event.name}",
            recipients=[email],
            body=f"Your slideshow '{event.name}' has finished rendering.\n\n"
                 f"Download your videos at:\n"
                 f"{current_app.config['APP_URL']}/events/{event.id}/output\n\n"
                 f"Slideshow Studio",
        )
        mail.send(msg)
    except Exception:
        pass
