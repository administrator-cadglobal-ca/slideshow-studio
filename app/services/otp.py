"""OTP generation, verification and SMS delivery."""
import secrets, string
from datetime import datetime, timezone, timedelta
from app.extensions import db
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


def send_sms(to_number: str, message: str) -> bool:
    """Send SMS via Twilio. Returns True on success."""
    from flask import current_app
    sid   = current_app.config.get("TWILIO_ACCOUNT_SID", "")
    token = current_app.config.get("TWILIO_AUTH_TOKEN",  "")
    from_  = current_app.config.get("TWILIO_FROM_NUMBER", "")

    # Detect placeholder / missing credentials
    placeholders = {"", "your-twilio-account-sid", "your-twilio-auth-token"}
    dev_mode = not all([sid, token, from_]) or sid in placeholders or token in placeholders

    if dev_mode:
        # Print OTP to console — works without Twilio configured
        print("\n" + "="*50)
        print(f"  [DEV OTP] To: {to_number}")
        print(f"  [DEV OTP] {message}")
        print("="*50 + "\n")
        return True

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        client.messages.create(body=message, from_=from_, to=to_number)
        return True
    except Exception as e:
        # Always fall back to console so login is never completely broken
        print("\n" + "="*50)
        print(f"  [OTP FALLBACK] Twilio failed: {e}")
        print(f"  [OTP FALLBACK] To: {to_number}")
        print(f"  [OTP FALLBACK] {message}")
        print("="*50 + "\n")
        return False


def send_otp_sms(user: User, otp: OTPCode) -> bool:
    msg = (f"Your Slideshow Studio code: {otp.code}\n"
           f"Valid for {OTP_TTL_MINUTES} minutes.")
    return send_sms(user.phone, msg)


def mask_phone(phone: str) -> str:
    """Return '+14031234567' as '+1403***4567'."""
    if not phone or len(phone) < 6:
        return phone
    return phone[:4] + "***" + phone[-4:]
