from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import RenderJob, Project
from app.services.storage import output_url

bp = Blueprint("renders", __name__)

@bp.route("/")
@login_required
def index():
    jobs = db.session.query(RenderJob)\
             .join(Project)\
             .filter(Project.user_id == current_user.id)\
             .order_by(RenderJob.created_at.desc()).limit(50).all()
    return render_template("renders/index.html", jobs=jobs)

@bp.route("/<job_id>")
@login_required
def show(job_id):
    job = db.session.get(RenderJob, job_id)
    if not job or job.event.user_id != current_user.id:
        abort(404)
    return render_template("renders/show.html", job=job, output_url=output_url)
