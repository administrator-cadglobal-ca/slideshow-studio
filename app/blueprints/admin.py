from flask          import Blueprint, render_template, redirect, url_for, \
                           request, flash, abort
from flask_login    import login_required, current_user
from app.extensions import db
from app.models.user import User, RegistrationRequest
from app.models.audit import AdminAuditLog, log_admin_action
from app.services import admin as admin_svc
from sqlalchemy import or_, desc, asc
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
    """Users admin: search, filter, sort, paginate."""
    q       = request.args.get("q", "").strip()
    status  = request.args.get("status", "").strip()
    role    = request.args.get("role", "").strip()
    sort    = request.args.get("sort", "recent").strip()
    page    = max(1, int(request.args.get("page", 1) or 1))
    per_pg  = 25

    query = User.query

    if q:
        pattern = f"%{q}%"
        query = query.filter(or_(
            User.email.ilike(pattern),
            User.first_name.ilike(pattern),
            User.last_name.ilike(pattern),
            User.phone.ilike(pattern),
        ))

    if status == "pending":
        query = query.filter(User.is_enabled == False)
    elif status == "active":
        query = query.filter(User.is_enabled == True,
                             User.is_active == True,
                             User.suspended_at.is_(None))
    elif status == "suspended":
        query = query.filter(User.suspended_at.isnot(None))
    elif status == "deactivated":
        query = query.filter(User.is_enabled == True,
                             User.is_active == False,
                             User.suspended_at.is_(None))

    if role:
        query = query.filter(User.role == role)

    sort_map = {
        "recent":     User.created_at.desc(),
        "oldest":     User.created_at.asc(),
        "name":       User.first_name.asc(),
        "last_login": User.last_login.desc().nullslast(),
        "email":      User.email.asc(),
    }
    query = query.order_by(sort_map.get(sort, User.created_at.desc()))

    pagination = query.paginate(page=page, per_page=per_pg, error_out=False)

    base_count_query = User.query
    if q:
        pattern = f"%{q}%"
        base_count_query = base_count_query.filter(or_(
            User.email.ilike(pattern),
            User.first_name.ilike(pattern),
            User.last_name.ilike(pattern),
            User.phone.ilike(pattern),
        ))
    if role:
        base_count_query = base_count_query.filter(User.role == role)

    counts = {
        "all":         base_count_query.count(),
        "pending":     base_count_query.filter(User.is_enabled == False).count(),
        "active":      base_count_query.filter(User.is_enabled == True,
                                               User.is_active == True,
                                               User.suspended_at.is_(None)).count(),
        "suspended":   base_count_query.filter(User.suspended_at.isnot(None)).count(),
        "deactivated": base_count_query.filter(User.is_enabled == True,
                                               User.is_active == False,
                                               User.suspended_at.is_(None)).count(),
    }

    return render_template(
        "admin/users.html",
        pagination = pagination,
        users      = pagination.items,
        counts     = counts,
        q          = q,
        status     = status,
        role       = role,
        sort       = sort,
    )









# G3 additions: user detail and admin action endpoints

@bp.route("/users/<int:user_id>")
@login_required
@admin_required
def user_detail(user_id):
    """User detail view. Full page (mobile) or side panel content (desktop)."""
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    recent_audit = AdminAuditLog.query\
        .filter_by(target_type="user", target_user_id=user.id)\
        .order_by(AdminAuditLog.created_at.desc())\
        .limit(10).all()

    ctx = {
        "user":         user,
        "recent_audit": recent_audit,
    }
    return render_template("admin/user_detail.html", **ctx)


def _require_user(user_id):
    """Fetch user or 404, and prevent operating on protected accounts."""
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    # Prevent admins from modifying super_admin accounts, and prevent
    # any admin from operating on themselves via these routes.
    if user.role == "super_admin" and current_user.role != "super_admin":
        abort(403)
    if user.id == current_user.id:
        flash("Use your profile page for changes to your own account.", "error")
        abort(400)
    return user


@bp.route("/users/<int:user_id>/suspend", methods=["POST"])
@login_required
@admin_required
def user_suspend(user_id):
    user   = _require_user(user_id)
    reason = request.form.get("reason", "").strip()
    admin_svc.suspend_user(user, reason=reason)
    flash(f"{user.full_name} suspended.", "success")
    return redirect(request.referrer or url_for("admin.users_list"))


@bp.route("/users/<int:user_id>/reactivate", methods=["POST"])
@login_required
@admin_required
def user_reactivate(user_id):
    user = _require_user(user_id)
    admin_svc.reactivate_user(user)
    flash(f"{user.full_name} reactivated.", "success")
    return redirect(request.referrer or url_for("admin.users_list"))


@bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@login_required
@admin_required
def user_deactivate(user_id):
    user = _require_user(user_id)
    admin_svc.deactivate_user(user)
    flash(f"{user.full_name} deactivated.", "success")
    return redirect(request.referrer or url_for("admin.users_list"))


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def user_delete(user_id):
    user  = _require_user(user_id)
    typed = request.form.get("confirm_email", "").strip().lower()
    if typed != user.email.lower():
        flash("Delete confirmation didn't match. No action taken.", "error")
        return redirect(request.referrer or url_for("admin.users_list"))
    name = user.full_name
    # Wipe user's storage directory first (best-effort)
    try:
        from app.services.storage import user_dir
        import shutil
        d = user_dir(user.id)
        if d.exists():
            shutil.rmtree(d)
    except Exception:
        pass
    admin_svc.delete_user(user)
    flash(f"{name} permanently deleted.", "success")
    return redirect(url_for("admin.users_list"))


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def user_change_role(user_id):
    user     = _require_user(user_id)
    new_role = request.form.get("role", "").strip().lower()
    if new_role not in ("user", "admin"):
        flash("Invalid role.", "error")
        return redirect(request.referrer or url_for("admin.users_list"))
    # Any admin can promote/demote for now. When role hierarchy is
    # reworked (Wave 7 proper), tighten this to require super_admin
    # for grants to admin role.
    admin_svc.change_role(user, new_role)
    flash(f"{user.full_name} role changed to {new_role}.", "success")
    return redirect(request.referrer or url_for("admin.users_list"))


@bp.route("/users/<int:user_id>/quota", methods=["POST"])
@login_required
@admin_required
def user_change_quota(user_id):
    user = _require_user(user_id)
    try:
        new_gb = float(request.form.get("quota_gb", "").strip())
        if new_gb <= 0 or new_gb > 10000:
            raise ValueError("out of range")
    except (ValueError, TypeError):
        flash("Quota must be a positive number of gigabytes.", "error")
        return redirect(request.referrer or url_for("admin.users_list"))
    new_bytes = int(new_gb * (1024 ** 3))
    admin_svc.change_quota(user, new_bytes)
    flash(f"{user.full_name} quota set to {new_gb:g} GB.", "success")
    return redirect(request.referrer or url_for("admin.users_list"))


@bp.route("/users/<int:user_id>/profile", methods=["POST"])
@login_required
@admin_required
def user_edit_profile(user_id):
    user = _require_user(user_id)
    admin_svc.edit_profile(
        user,
        first_name   = request.form.get("first_name", "").strip() or None,
        last_name    = request.form.get("last_name",  "").strip() or None,
        email        = request.form.get("email",       "").strip().lower() or None,
        phone        = request.form.get("phone",       "").strip() or None,
        notify_email = request.form.get("notify_email","").strip().lower() or None,
        admin_notes  = request.form.get("admin_notes", "").strip() or None,
    )
    flash("Profile updated.", "success")
    return redirect(request.referrer or url_for("admin.user_detail", user_id=user_id))


@bp.route("/users/<int:user_id>/reset-otp", methods=["POST"])
@login_required
@admin_required
def user_reset_otp(user_id):
    user = _require_user(user_id)
    admin_svc.reset_otp(user)
    flash(f"OTP codes for {user.full_name} invalidated.", "success")
    return redirect(request.referrer or url_for("admin.users_list"))
