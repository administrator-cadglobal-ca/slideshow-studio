from flask       import Blueprint, render_template, redirect, url_for, \
                        request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models.user import User, RegistrationRequest

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        first   = request.form.get("first_name", "").strip()
        last    = request.form.get("last_name",  "").strip()
        email   = request.form.get("email",  "").strip().lower()
        phone   = request.form.get("phone",  "").strip()
        code    = request.form.get("discount_code", "").strip().upper()
        message = request.form.get("message", "").strip()

        if not all([first, last, email, phone]):
            flash("Please fill in all required fields.", "error")
            return render_template("auth/register.html", **request.form)

        # Duplicate check
        if User.query.filter_by(email=email).first() or \
           RegistrationRequest.query.filter_by(email=email, status="pending").first():
            flash("An account or request already exists for that email.", "error")
            return render_template("auth/register.html", **request.form)

        req = RegistrationRequest(
            first_name    = first,
            last_name     = last,
            email         = email,
            phone         = phone,
            discount_code = code or None,
            message       = message or None,
        )
        db.session.add(req)
        db.session.commit()
        return redirect(url_for("auth.register_done"))

    return render_template("auth/register.html")


@bp.route("/register/done")
def register_done():
    return render_template("auth/register_done.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user  = User.query.filter_by(email=email, is_enabled=True, is_active=True).first()

        if not user:
            flash("No active account found for that email.", "error")
            return render_template("auth/login.html", email=email)

        from app.services.otp import issue_otp, send_otp_sms
        otp = issue_otp(user)
        send_otp_sms(user, otp)
        session["pending_user_id"] = user.id
        return redirect(url_for("auth.verify"))

    return render_template("auth/login.html")


@bp.route("/verify", methods=["GET", "POST"])
def verify():
    user_id = session.get("pending_user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, user_id)
    if not user:
        return redirect(url_for("auth.login"))

    from app.services.otp import mask_phone
    masked = mask_phone(user.phone)

    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        from app.services.otp import verify_otp
        ok, reason = verify_otp(user, code)

        if ok:
            from datetime import datetime, timezone
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            session.pop("pending_user_id", None)
            session.permanent = True
            login_user(user, remember=False)
            next_url = request.args.get("next") or url_for("dashboard.index")
            return redirect(next_url)
        else:
            flash(reason, "error")

    return render_template("auth/verify.html", masked_phone=masked)


@bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    user_id = session.get("pending_user_id")
    if user_id:
        user = db.session.get(User, user_id)
        if user:
            from app.services.otp import issue_otp, send_otp_sms
            otp = issue_otp(user)
            send_otp_sms(user, otp)
            flash("New code sent.", "info")
    return redirect(url_for("auth.verify"))


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/google/connect")
@login_required
def google_connect():
    flash("Google OAuth not configured yet.", "info")
    return redirect(url_for("dashboard.index"))


@bp.route("/google/callback")
def google_callback():
    return redirect(url_for("dashboard.index"))


@bp.route("/google/disconnect")
@login_required
def google_disconnect():
    current_user.google_access_token  = None
    current_user.google_refresh_token = None
    current_user.google_email         = None
    db.session.commit()
    flash("Google account disconnected.", "info")
    return redirect(url_for("dashboard.profile"))
