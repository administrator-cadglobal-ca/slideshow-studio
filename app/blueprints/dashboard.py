from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Project, RenderJob
from datetime import datetime, timezone

bp = Blueprint("dashboard", __name__)

LOOP_COLORS = ["#1e3a52","#2a1e3a","#0f3a2a","#3a1e1e","#1e2e3a","#2a3a1e"]

@bp.route("/")
@login_required
def index():
    projects = db.session.query(Project)\
                 .filter_by(user_id=current_user.id)\
                 .order_by(Project.updated_at.desc()).all()
    active_job = db.session.query(RenderJob)\
                   .join(Project)\
                   .filter(Project.user_id == current_user.id,
                           RenderJob.status.in_(["queued","running"]))\
                   .first()
    from app.models import AudioFile, RenderOutput
    audio_count   = db.session.query(AudioFile).filter_by(user_id=current_user.id).count()
    total_outputs = db.session.query(RenderOutput)\
                     .join(RenderJob).join(Project)\
                     .filter(Project.user_id==current_user.id).count()
    now_hour = datetime.now().hour
    return render_template("dashboard/index.html",
        projects=projects, active_job=active_job,
        audio_count=audio_count, total_outputs=total_outputs,
        loop_colors=LOOP_COLORS, now_hour=now_hour)

@bp.route("/profile")
@login_required
def profile():
    return render_template("dashboard/profile.html")
