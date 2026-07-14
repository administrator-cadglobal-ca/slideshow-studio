from flask          import Blueprint, render_template, redirect, url_for, \
                           request, flash, abort
from flask_login    import login_required, current_user
from app.extensions import db
from app.models.user import User, RegistrationRequest
from functools      import wraps

bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@bp.route("/")
@login_required
@admin_required
def index():
    from app.models import RenderJob
    pending = RegistrationRequest.query.filter_by(status="pending")\
                .order_by(RegistrationRequest.created_at.desc()).all()
    users   = User.query.order_by(User.created_at.desc()).all()
    total_renders = db.session.query(RenderJob).count()
    return render_template("admin/index.html",
        pending=pending, users=users, total_renders=total_renders)


@bp.route("/requests")
@login_required
@admin_required
def requests_list():
    requests = RegistrationRequest.query\
                 .order_by(RegistrationRequest.created_at.desc()).all()
    return render_template("admin/requests.html", requests=requests)


@bp.route("/requests/<int:req_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_request(req_id):
    req = db.session.get(RegistrationRequest, req_id)
    if not req or req.status != "pending":
        abort(404)

    # Create the user account
    user = User(
        email      = req.email,
        first_name = req.first_name,
        last_name  = req.last_name,
        phone      = req.phone,
        role       = "user",
        is_enabled = True,
        is_active  = True,
    )
    db.session.add(user)

    from datetime import datetime, timezone
    req.status      = "approved"
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.now(timezone.utc)
    db.session.commit()

    # Send SMS
    try:
        from app.services.otp import send_sms
        send_sms(req.phone,
            f"Hi {req.first_name}! Your Slideshow Studio account is ready. "
            f"Sign in at {request.host_url}auth/login")
    except Exception:
        pass

    flash(f"Approved {req.full_name} — account created.", "success")
    return redirect(url_for("admin.requests_list"))


@bp.route("/requests/<int:req_id>/reject", methods=["POST"])
@login_required
@admin_required
def reject_request(req_id):
    req = db.session.get(RegistrationRequest, req_id)
    if not req or req.status != "pending":
        abort(404)

    from datetime import datetime, timezone
    note        = request.form.get("note", "").strip()
    req.status      = "rejected"
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.now(timezone.utc)
    req.review_note = note
    db.session.commit()

    try:
        from app.services.otp import send_sms
        msg = f"Hi {req.first_name}, your Slideshow Studio request was not approved."
        if note:
            msg += f" Reason: {note}"
        send_sms(req.phone, msg)
    except Exception:
        pass

    flash(f"Rejected {req.full_name}.", "info")
    return redirect(url_for("admin.requests_list"))


@bp.route("/users")
@login_required
@admin_required
def users_list():
    users = User.query.order_by(User.created_at).all()
    return render_template("admin/users.html", users=users)


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_user(user_id):
    user = db.session.get(User, user_id)
    if not user or user.id == current_user.id:
        abort(400)
    user.is_active = not user.is_active
    db.session.commit()
    action = "reactivated" if user.is_active else "suspended"
    flash(f"{user.full_name} {action}.", "success")
    return redirect(url_for("admin.users_list"))


@bp.route("/users/<int:user_id>/quota", methods=["POST"])
@login_required
@admin_required
def set_quota(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    gb = float(request.form.get("quota_gb", 20))
    user.quota_bytes = int(gb * 1024 ** 3)
    db.session.commit()
    flash(f"Quota for {user.full_name} set to {gb:.0f} GB.", "success")
    return redirect(url_for("admin.users_list"))


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def set_role(user_id):
    user = db.session.get(User, user_id)
    if not user or user.id == current_user.id:
        abort(400)
    role = request.form.get("role", "user")
    if role not in ("user", "admin"):
        abort(400)
    user.role = role
    db.session.commit()
    label = "an admin" if role == "admin" else "a regular user"
    flash(f"{user.full_name} is now {label}.", "success")
    return redirect(url_for("admin.users_list"))


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user or user.id == current_user.id or user.is_active:
        abort(400)
    from app.services.storage import user_dir
    import shutil
    try:
        d = user_dir(user.id)
        if d.exists():
            shutil.rmtree(d)
    except Exception:
        pass
    db.session.delete(user)
    db.session.commit()
    flash("User deleted.", "success")
    return redirect(url_for("admin.users_list"))
