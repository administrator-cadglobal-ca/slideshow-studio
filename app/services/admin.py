"""Admin action service - all state-changing operations on user records.

Each function takes the target user, applies the change, writes an audit
entry, and commits. Callers should catch exceptions and flash errors.
"""
from datetime import datetime, timezone
from flask_login import current_user
from app.extensions import db
from app.models.user import User, OTPCode
from app.models.audit import log_admin_action


def _now():
    return datetime.now(timezone.utc)


def approve_user(user: User) -> None:
    user.is_enabled  = True
    user.is_active   = True
    user.approved_by = current_user.id
    user.approved_at = _now()
    log_admin_action("approved", target_user_id=user.id)
    db.session.commit()


def suspend_user(user: User, reason: str = "") -> None:
    user.is_active         = False
    user.suspended_at      = _now()
    user.suspended_by      = current_user.id
    user.suspension_reason = reason or None
    # Invalidate all outstanding OTPs so the suspended user can't consume one
    OTPCode.query.filter_by(user_id=user.id).delete()
    log_admin_action("suspended", target_user_id=user.id, payload={"reason": reason})
    db.session.commit()


def reactivate_user(user: User) -> None:
    user.is_active         = True
    user.suspended_at      = None
    user.suspended_by      = None
    user.suspension_reason = None
    log_admin_action("reactivated", target_user_id=user.id)
    db.session.commit()


def deactivate_user(user: User) -> None:
    user.is_active       = False
    user.deactivated_at  = _now()
    user.deactivated_by  = current_user.id
    OTPCode.query.filter_by(user_id=user.id).delete()
    log_admin_action("deactivated", target_user_id=user.id)
    db.session.commit()


def delete_user(user: User) -> None:
    """Hard delete. Caller must confirm this is a real deletion."""
    email = user.email
    OTPCode.query.filter_by(user_id=user.id).delete()
    log_admin_action("deleted", target_user_id=user.id, payload={"email": email})
    db.session.delete(user)
    db.session.commit()


def change_role(user: User, new_role: str) -> None:
    old_role = user.role
    user.role = new_role
    log_admin_action("role_changed", target_user_id=user.id,
                     payload={"from": old_role, "to": new_role})
    db.session.commit()


def change_quota(user: User, new_quota_bytes: int) -> None:
    old_quota = user.quota_bytes
    user.quota_bytes = new_quota_bytes
    log_admin_action("quota_changed", target_user_id=user.id,
                     payload={"from_bytes": old_quota, "to_bytes": new_quota_bytes})
    db.session.commit()


def edit_profile(user: User, first_name: str = None, last_name: str = None,
                 email: str = None, phone: str = None, notify_email: str = None,
                 admin_notes: str = None) -> None:
    changes = {}
    if first_name   is not None and first_name   != user.first_name:   changes["first_name"]   = [user.first_name,   first_name]; user.first_name   = first_name
    if last_name    is not None and last_name    != user.last_name:    changes["last_name"]    = [user.last_name,    last_name];  user.last_name    = last_name
    if email        is not None and email        != user.email:        changes["email"]        = [user.email,        email];      user.email        = email
    if phone        is not None and phone        != user.phone:        changes["phone"]        = [user.phone,        phone];      user.phone        = phone or None
    if notify_email is not None and notify_email != user.notify_email: changes["notify_email"] = [user.notify_email, notify_email]; user.notify_email = notify_email or None
    if admin_notes  is not None and admin_notes  != user.admin_notes:  changes["admin_notes"]  = ["<updated>",        "<updated>"]; user.admin_notes  = admin_notes or None

    if changes:
        log_admin_action("profile_edited", target_user_id=user.id, payload={"changes": changes})
        db.session.commit()


def reset_otp(user: User) -> None:
    """Invalidate all active OTP codes for this user."""
    n = OTPCode.query.filter_by(user_id=user.id).delete()
    log_admin_action("otp_reset", target_user_id=user.id, payload={"invalidated_count": n})
    db.session.commit()