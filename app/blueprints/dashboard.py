from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Event, RenderJob
from datetime import datetime, timezone
bp = Blueprint("dashboard", __name__)
LOOP_COLORS = ["#1e3a52","#2a1e3a","#0f3a2a","#3a1e1e","#1e2e3a","#2a3a1e"]

@bp.route("/")
@login_required
def index():
    from app.models import AudioFile, AudioClip, RenderOutput, Library, Playlist
    from app.models.event import ShareToken, RenderShare

    events = db.session.query(Event)\
                 .filter_by(user_id=current_user.id)\
                 .order_by(Event.updated_at.desc()).all()

    active_job = db.session.query(RenderJob)\
                   .join(Event)\
                   .filter(Event.user_id == current_user.id,
                           RenderJob.status.in_(["queued","running"]))\
                   .first()

    # Aggregate stats
    audio_count   = db.session.query(AudioFile).filter_by(user_id=current_user.id).count()
    clip_count    = db.session.query(AudioClip)\
                      .join(AudioFile, AudioClip.song_id == AudioFile.id)\
                      .filter(AudioFile.user_id == current_user.id).count()
    library_count = db.session.query(Library).filter_by(user_id=current_user.id).count()
    playlist_count= db.session.query(Playlist).filter_by(user_id=current_user.id).count()
    total_outputs = db.session.query(RenderOutput)\
                     .join(RenderJob).join(Event)\
                     .filter(Event.user_id == current_user.id).count()

    event_ids = [e.id for e in events]

    # Per-event summaries
    event_summaries = []
    total_slideshow_shares = 0
    total_video_shares = 0

    for evt in events:
        # Photos count
        from app.models import Photo
        photo_count = db.session.query(Photo).filter_by(event_id=evt.id).count()

        # Slideshow shares (ShareToken share_type='public')
        slideshow_shares = db.session.query(ShareToken)\
                             .filter_by(event_id=evt.id)\
                             .filter(ShareToken.share_type == 'public')\
                             .order_by(ShareToken.created_at.desc()).all()

        # Video shares (RenderShare)
        video_shares = db.session.query(RenderShare)\
                        .filter_by(event_id=evt.id)\
                        .order_by(RenderShare.created_at.desc()).all()

        # Render count
        render_output_count = db.session.query(RenderOutput)\
                                .join(RenderJob).filter(RenderJob.event_id == evt.id).count()

        total_slideshow_shares += len(slideshow_shares)
        total_video_shares += len(video_shares)

        event_summaries.append({
            "event": evt,
            "photo_count": photo_count,
            "slideshow_shares": slideshow_shares,
            "video_shares": video_shares,
            "render_count": render_output_count,
        })

    now_hour = datetime.now().hour

    return render_template("dashboard/index.html",
        events=events,
        event_summaries=event_summaries,
        active_job=active_job,
        audio_count=audio_count,
        clip_count=clip_count,
        library_count=library_count,
        playlist_count=playlist_count,
        total_outputs=total_outputs,
        total_slideshow_shares=total_slideshow_shares,
        total_video_shares=total_video_shares,
        loop_colors=LOOP_COLORS,
        now_hour=now_hour)


@bp.route("/profile")
@login_required
def profile():
    return render_template("dashboard/profile.html")