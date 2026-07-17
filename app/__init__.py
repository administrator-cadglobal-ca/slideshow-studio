from flask import Flask
from config.settings import config
from app.extensions  import db, login_manager, mail


def create_app(env: str = "default") -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config[env])

    # ── Extensions ─────────────────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    # Celery is optional — only init if Redis is reachable
    try:
        from app.extensions import celery_app
        from celery import Celery
        celery_app.conf.update(
            broker_url     = app.config["CELERY_BROKER_URL"],
            result_backend = app.config["CELERY_RESULT_BACKEND"],
        )
        class ContextTask(celery_app.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        celery_app.Task = ContextTask
    except Exception:
        pass

    # ── Blueprints ─────────────────────────────────────────────────────────────
    from app.blueprints.auth      import bp as auth_bp
    from app.blueprints.dashboard import bp as dash_bp
    from app.blueprints.events  import bp as proj_bp
    from app.blueprints.audio     import bp as audio_bp
    from app.blueprints.renders   import bp as render_bp
    from app.blueprints.admin     import bp as admin_bp
    from app.blueprints.api       import bp as api_bp
    from app.blueprints.share     import bp as share_bp

    app.register_blueprint(auth_bp,   url_prefix="/auth")
    app.register_blueprint(dash_bp,   url_prefix="/")
    app.register_blueprint(proj_bp,   url_prefix="/events")
    app.register_blueprint(audio_bp,  url_prefix="/audio")
    app.register_blueprint(render_bp, url_prefix="/renders")
    app.register_blueprint(admin_bp,  url_prefix="/admin")
    app.register_blueprint(api_bp,    url_prefix="/api/v1")
    app.register_blueprint(share_bp)  # /s/<token> - no prefix

    # ── Database ────────────────────────────────────────────────────────────────
    with app.app_context():
        db.create_all()
        _seed_admin(app)

    # ── Template helpers ────────────────────────────────────────────────────────
    _register_template_helpers(app)

    # ── Context processors ────────────────────────────────────
    @app.context_processor
    def inject_admin_counts():
        """Make pending-request count available in every template.
        Only queries when user is authenticated admin, to avoid load."""
        from flask_login import current_user
        if not current_user.is_authenticated:
            return {}
        if getattr(current_user, "role", None) not in ("admin", "super_admin"):
            return {}
        from app.models.user import RegistrationRequest
        try:
            n = RegistrationRequest.query.filter_by(status="pending").count()
        except Exception:
            n = 0
        return {"pending_requests_count": n}

    return app


def _seed_admin(app: Flask):
    """Create the admin account on first run if ADMIN_EMAIL is set."""
    from app.models import User
    admin_email = app.config.get("ADMIN_EMAIL", "")
    admin_phone = app.config.get("ADMIN_PHONE", "+10000000001")
    if not admin_email:
        return
    existing = db.session.query(User).filter_by(email=admin_email).first()
    if not existing:
        admin = User(
            email      = admin_email,
            first_name = "Gurmeet",
            last_name  = "Singh",
            phone      = admin_phone,
            role       = "admin",
            is_enabled = True,
            is_active  = True,
            quota_bytes= 100 * 1024 ** 3,
        )
        db.session.add(admin)
        db.session.commit()
        print("\n" + "="*55)
        print(f"  [SEED] Admin created: {admin_email}")
        print(f"  [SEED] Sign in at http://localhost:5000/auth/login")
        print(f"  [SEED] OTP will print here in the console")
        print("="*55 + "\n")
    else:
        # Update phone if ADMIN_PHONE is set and different
        if admin_phone != "+10000000001" and existing.phone != admin_phone:
            existing.phone = admin_phone
            db.session.commit()
            print(f"[SEED] Admin phone updated to {admin_phone}")


def _register_template_helpers(app: Flask):
    import humanize
    from datetime import datetime, timezone

    @app.template_filter("parse_time")
    def parse_time_filter(s):
        try:
            if not s: return 0
            parts = str(s).strip().split(":")
            if len(parts) == 2: return int(parts[0]) * 60 + float(parts[1])
            if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            return float(s)
        except Exception:
            return 0

    @app.template_filter("filesizeformat")
    def filesizeformat_filter(value):
        try:
            return humanize.naturalsize(int(value or 0), binary=True)
        except Exception:
            return "0 B"

    @app.template_filter("dateformat")
    def dateformat_filter(dt, fmt="%b %d, %Y"):
        """Cross-platform date formatting — strips leading zero from day."""
        if not dt:
            return ""
        s = dt.strftime(fmt)
        # Remove leading zero from day number on all platforms
        import re
        s = re.sub(r'(?<=\s)0(\d)', r'\1', s)  # "Jul 07" → "Jul 7"
        return s

    @app.template_filter("naturaltime")
    def naturaltime_filter(dt):
        try:
            if not dt: return ""
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return humanize.naturaltime(datetime.now(timezone.utc) - dt)
        except Exception:
            return ""

    @app.template_filter("tojson")
    def tojson_filter(value):
        import json
        return json.dumps(value, default=str)

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from app.models.user import RegistrationRequest

        def pending_requests_count():
            try:
                if current_user.is_authenticated and current_user.is_admin:
                    return RegistrationRequest.query.filter_by(status="pending").count()
            except Exception:
                pass
            return 0

        return dict(pending_requests_count=pending_requests_count)
