"""OTP generation, verification and delivery."""
import secrets, string
from datetime import datetime, timezone, timedelta
from app.extensions import db, mail
from app.models.user import OTPCode, User


CHARS = string.ascii_uppercase + string.digits   # A-Z 0-9
OTP_TTL_MINUTES  = 10
OTP_MAX_ATTEMPTS = 5


def generate_otp() -> str:
    return "".join(secrets.choice(CHARS) for _ in range(8))


def issue_otp(user: User) -> OTPCode:
    """Invalidate old codes and create a fresh one."""
    db.session.query(OTPCode).filter_by(user_id=user.id).delete()
    otp = OTPCode(
        user_id    = user.id,
        code       = generate_otp(),
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.session.add(otp)
    db.session.commit()
    return otp


def verify_otp(user: User, code: str) -> tuple[bool, str]:
    """
    Returns (True, "") on success.
    Returns (False, reason) on failure.
    """
    otp = db.session.query(OTPCode)\
            .filter_by(user_id=user.id)\
            .order_by(OTPCode.created_at.desc())\
            .first()

    if not otp:
        return False, "No code found. Request a new one."

    if otp.is_used:
        return False, "Code already used. Request a new one."

    if otp.is_expired:
        return False, "Code expired. Request a new one."

    if otp.attempts >= OTP_MAX_ATTEMPTS:
        return False, "Too many attempts. Request a new code."

    if otp.code != code.upper().strip():
        otp.attempts += 1
        db.session.commit()
        remaining = OTP_MAX_ATTEMPTS - otp.attempts
        return False, f"Incorrect code. {remaining} attempt(s) remaining."

    otp.used_at = datetime.now(timezone.utc)
    db.session.commit()
    return True, ""


def send_otp_email(user: User, otp: OTPCode) -> bool:
    """
    Send the OTP to the user by email via Flask-Mail (Hostinger SMTP).
    Falls back to console print if mail send raises. Returns True on success.
    """
    from flask import current_app, render_template
    from flask_mail import Message

    try:
        msg = Message(
            subject    = f"Your Slideshow Studio code: {otp.code}",
            recipients = [user.email],
            body       = render_template("email/otp.txt",  user=user, otp=otp, ttl=OTP_TTL_MINUTES),
            html       = render_template("email/otp.html", user=user, otp=otp, ttl=OTP_TTL_MINUTES),
        )
        mail.send(msg)
        current_app.logger.info(f"OTP email sent to {user.email}")
        return True
    except Exception as e:
        # Fall back to console so login is never fully broken during dev/incidents
        current_app.logger.error(f"OTP email failed for {user.email}: {e}")
        print("\n" + "="*55)
        print(f"  [OTP EMAIL FALLBACK] To: {user.email}")
        print(f"  [OTP EMAIL FALLBACK] Code: {otp.code}")
        print(f"  [OTP EMAIL FALLBACK] Reason: {e}")
        print("="*55 + "\n")
        return False


def mask_email(email: str) -> str:
    """Return 'gxsingh@yahoo.com' as 'gxs***@yahoo.com'."""
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 3:
        masked_local = local[0] + "***"
    else:
        masked_local = local[:3] + "***"
    return f"{masked_local}@{domain}"


# ═══════════════════════════════════════════════════════════════════════
# Legacy SMS path — kept for reference but no longer called by auth flow.
# Delete this whole section after B4 is stable in production for a week.
# ═══════════════════════════════════════════════════════════════════════

def send_sms(to_number: str, message: str) -> bool:
    """DEPRECATED. Kept temporarily; call send_otp_email instead."""
    from flask import current_app
    sid   = current_app.config.get("TWILIO_ACCOUNT_SID", "")
    token = current_app.config.get("TWILIO_AUTH_TOKEN",  "")
    from_  = current_app.config.get("TWILIO_FROM_NUMBER", "")
    placeholders = {"", "your-twilio-account-sid", "your-twilio-auth-token"}
    dev_mode = not all([sid, token, from_]) or sid in placeholders or token in placeholders
    if dev_mode:
        print("\n" + "="*50)
        print(f"  [DEV OTP - SMS DEPRECATED] To: {to_number}")
        print(f"  [DEV OTP - SMS DEPRECATED] {message}")
        print("="*50 + "\n")
        return True
    try:
        from twilio.rest import Client
        client = Client(sid, token)
        client.messages.create(body=message, from_=from_, to=to_number)
        return True
    except Exception as e:
        print(f"  [SMS FALLBACK] Twilio failed: {e}")
        return False


def send_otp_sms(user: User, otp: OTPCode) -> bool:
    """DEPRECATED. Call send_otp_email instead."""
    msg = (f"Your Slideshow Studio code: {otp.code}\n"
           f"Valid for {OTP_TTL_MINUTES} minutes.")
    return send_sms(user.phone, msg)


def mask_phone(phone: str) -> str:
    """DEPRECATED. Kept for backwards compat; prefer mask_email."""
    if not phone or len(phone) < 6:
        return phone
    return phone[:4] + "***" + phone[-4:]