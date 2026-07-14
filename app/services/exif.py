"""
exif.py — Extract EXIF metadata from photos, including GPS.

Reads:
  - Date/time taken (DateTimeOriginal)
  - Camera make and model (Apple iPhone 15 Pro, Samsung Galaxy S24, etc.)
  - Lens, focal length, 35mm equivalent
  - Aperture (f/stop), shutter speed, ISO
  - Flash, exposure mode, white balance, metering
  - GPS: latitude, longitude, altitude, speed, direction
  - Reverse geocoding: GPS coords → "Banff, AB, Canada"
  - Color space, software version

Works with: JPEG, HEIC (if pillow-heif installed), PNG with EXIF
GPS data is especially rich from iPhones.
"""

from __future__ import annotations
from pathlib import Path
from datetime import datetime
from fractions import Fraction
import math
import logging

log = logging.getLogger(__name__)


# ── Main extraction entry point ────────────────────────────────────────────────

def extract_metadata(image_path: str | Path) -> dict:
    """
    Extract all EXIF metadata from an image file.
    Returns a flat dict of all found fields. Missing fields are None.
    Never raises — returns empty dict on failure.
    """
    path = Path(image_path)
    result = _empty_meta()

    try:
        from PIL import Image, ExifTags, TiffImagePlugin
        img = Image.open(path)

        # Get raw EXIF dict
        raw = _get_raw_exif(img)
        if not raw:
            return result

        # Build tag-name → value map
        exif = {}
        for tag_id, value in raw.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
            exif[tag_name] = value

        # ── Date & time ───────────────────────────────────────────────────────
        for date_field in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
            val = exif.get(date_field)
            if val:
                dt = _parse_exif_date(str(val))
                if dt:
                    result["exif_date"]     = dt
                    result["exif_date_str"] = dt.strftime("%b %d, %Y  %-I:%M %p")
                    break

        # ── Camera ────────────────────────────────────────────────────────────
        result["camera_make"]  = _clean(exif.get("Make"))
        result["camera_model"] = _clean(exif.get("Model"))
        result["lens_model"]   = _clean(exif.get("LensModel") or exif.get("LensSpecification"))
        result["software"]     = _clean(exif.get("Software"))
        result["color_space"]  = _parse_color_space(exif.get("ColorSpace"))

        # Focal length
        fl = exif.get("FocalLength")
        if fl:
            result["focal_length"] = f"{_to_float(fl):.1f} mm"
        fl35 = exif.get("FocalLengthIn35mmFilm")
        if fl35:
            result["focal_length_35"] = f"{int(fl35)} mm"

        # Aperture (FNumber)
        fn = exif.get("FNumber")
        if fn:
            result["aperture"] = f"f/{_to_float(fn):.1f}"

        # Shutter speed (ExposureTime)
        et = exif.get("ExposureTime")
        if et:
            result["shutter_speed"] = _format_shutter(_to_float(et))

        # ISO
        iso = exif.get("ISOSpeedRatings") or exif.get("ISO")
        if iso:
            result["iso"] = int(iso) if isinstance(iso, (int, float)) else int(str(iso).split()[0])

        # Flash
        flash_val = exif.get("Flash")
        if flash_val is not None:
            result["flash"] = _parse_flash(int(flash_val))

        # Exposure / white balance / metering
        exp_mode = exif.get("ExposureMode")
        if exp_mode is not None:
            result["exposure_mode"] = {0:"Auto", 1:"Manual", 2:"Auto bracket"}.get(int(exp_mode), str(exp_mode))

        wb = exif.get("WhiteBalance")
        if wb is not None:
            result["white_balance"] = {0:"Auto", 1:"Manual"}.get(int(wb), str(wb))

        mm = exif.get("MeteringMode")
        if mm is not None:
            result["metering_mode"] = {
                0:"Unknown",1:"Average",2:"Center-weighted",3:"Spot",
                4:"Multi-spot",5:"Pattern",6:"Partial"
            }.get(int(mm), str(mm))

        # ── GPS ────────────────────────────────────────────────────────────────
        gps_info = exif.get("GPSInfo")
        if gps_info:
            gps = _parse_gps(gps_info)
            result.update(gps)

    except Exception as e:
        log.debug(f"EXIF extraction failed for {path}: {e}")

    return result


# ── Reverse geocoding ─────────────────────────────────────────────────────────

def reverse_geocode(lat: float, lon: float) -> dict:
    """
    Convert GPS coordinates to a human-readable location.
    Uses Nominatim (OpenStreetMap) — free, no API key.
    Returns: {"location": "Banff, AB, Canada", "place": "Banff", "country": "Canada"}
    """
    result = {"gps_location": "", "gps_place": "", "gps_country": ""}
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderServiceError
        import time

        geo = Nominatim(user_agent="slideshow-studio/1.0", timeout=5)
        location = geo.reverse((lat, lon), language="en", exactly_one=True)

        if location:
            addr = location.raw.get("address", {})
            parts = []

            # Build short readable address
            city  = (addr.get("city") or addr.get("town") or
                     addr.get("village") or addr.get("hamlet") or
                     addr.get("suburb") or addr.get("neighbourhood") or "")
            state = (addr.get("state") or addr.get("province") or
                     addr.get("region") or "")
            country = addr.get("country") or ""
            country_code = addr.get("country_code", "").upper()

            place = city or addr.get("county") or ""
            if place: parts.append(place)

            # Use state abbreviation for known countries
            if state and country_code in ("US", "CA", "AU"):
                state_abbr = addr.get("ISO3166-2-lvl4", "").split("-")[-1]
                parts.append(state_abbr if state_abbr else state)
            elif state and state != country:
                parts.append(state)

            if country: parts.append(country)

            result["gps_location"] = ", ".join(p for p in parts if p)
            result["gps_place"]    = place
            result["gps_country"]  = country

    except ImportError:
        log.debug("geopy not installed — reverse geocoding skipped")
    except Exception as e:
        log.debug(f"Reverse geocode failed ({lat},{lon}): {e}")

    return result


# ── GPS parsing ────────────────────────────────────────────────────────────────

def _parse_gps(gps_info: dict) -> dict:
    """Parse GPSInfo IFD tag dict from PIL EXIF."""
    from PIL import ExifTags
    result = {}

    # Build tag-name → value for GPS tags
    GPS_TAGS = ExifTags.GPSTAGS
    gps = {}
    for tag_id, val in gps_info.items():
        tag_name = GPS_TAGS.get(tag_id, str(tag_id))
        gps[tag_name] = val

    # Latitude
    lat_raw = gps.get("GPSLatitude")
    lat_ref = gps.get("GPSLatitudeRef", "N")
    lon_raw = gps.get("GPSLongitude")
    lon_ref = gps.get("GPSLongitudeRef", "E")

    if lat_raw and lon_raw:
        lat = _dms_to_decimal(lat_raw)
        lon = _dms_to_decimal(lon_raw)
        if lat_ref in ("S", "s"): lat = -lat
        if lon_ref in ("W", "w"): lon = -lon
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            result["gps_lat"] = round(lat, 7)
            result["gps_lon"] = round(lon, 7)

    # Altitude
    alt_raw = gps.get("GPSAltitude")
    alt_ref = gps.get("GPSAltitudeRef", 0)   # 0=above sea level, 1=below
    if alt_raw is not None:
        alt = _to_float(alt_raw)
        if alt_ref == 1: alt = -alt
        result["gps_alt"] = round(alt, 1)

    # Speed (in km/h — iPhone reports in km/h with ref "K")
    speed_raw = gps.get("GPSSpeed")
    speed_ref = gps.get("GPSSpeedRef", "K")
    if speed_raw is not None:
        spd = _to_float(speed_raw)
        if speed_ref == "M":   spd *= 1.60934   # miles → km
        elif speed_ref == "N": spd *= 1.852      # knots → km
        result["gps_speed"] = round(spd, 1)

    # Direction (compass bearing)
    dir_raw = gps.get("GPSImgDirection") or gps.get("GPSTrack")
    if dir_raw is not None:
        result["gps_direction"] = round(_to_float(dir_raw), 1)

    return result


def _dms_to_decimal(dms) -> float:
    """Convert (degrees, minutes, seconds) tuple to decimal degrees."""
    if not dms or len(dms) < 3:
        return 0.0
    d = _to_float(dms[0])
    m = _to_float(dms[1])
    s = _to_float(dms[2])
    return d + m / 60.0 + s / 3600.0


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_raw_exif(img) -> dict:
    """Get raw EXIF dict from PIL image."""
    try:
        exif_data = img._getexif()
        if exif_data:
            return exif_data
    except AttributeError:
        pass
    try:
        from PIL import TiffImagePlugin
        info = img.tag_v2
        if info:
            return dict(info)
    except Exception:
        pass
    return {}


def _to_float(val) -> float:
    """Convert IFDRational, Fraction, tuple, or numeric to float."""
    try:
        if hasattr(val, "numerator") and hasattr(val, "denominator"):
            return float(val.numerator) / float(val.denominator) if val.denominator else 0.0
        if isinstance(val, tuple) and len(val) == 2:
            return float(val[0]) / float(val[1]) if val[1] else 0.0
        return float(val)
    except Exception:
        return 0.0


def _parse_exif_date(s: str) -> datetime | None:
    """Parse EXIF date string '2026:06:15 15:42:00'."""
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    return None


def _format_shutter(seconds: float) -> str:
    """Format shutter speed as a fraction e.g. '1/500' or '2.5'."""
    if seconds <= 0:
        return ""
    if seconds >= 1:
        return f"{seconds:.1f}".rstrip("0").rstrip(".")
    denom = round(1 / seconds)
    return f"1/{denom}"


def _parse_flash(val: int) -> str:
    """Decode EXIF Flash tag bitmask."""
    fired = val & 0x01
    if not fired:
        return "No flash"
    return_val = (val >> 1) & 0x03
    if return_val == 2:
        return "Flash fired, no return"
    if return_val == 3:
        return "Flash fired, return detected"
    return "Flash fired"


def _parse_color_space(val) -> str:
    if val is None:
        return ""
    return {1: "sRGB", 65535: "Uncalibrated", 2: "Adobe RGB"}.get(int(val), "")


def _clean(val) -> str | None:
    """Strip whitespace/nulls from EXIF strings."""
    if val is None:
        return None
    s = str(val).strip().strip("\x00")
    return s if s else None


def _empty_meta() -> dict:
    return {
        "exif_date": None, "exif_date_str": None,
        "camera_make": None, "camera_model": None, "lens_model": None,
        "focal_length": None, "focal_length_35": None,
        "aperture": None, "shutter_speed": None, "iso": None,
        "flash": None, "exposure_mode": None,
        "white_balance": None, "metering_mode": None,
        "gps_lat": None, "gps_lon": None, "gps_alt": None,
        "gps_speed": None, "gps_direction": None,
        "gps_location": None, "gps_place": None, "gps_country": None,
        "color_space": None, "software": None,
    }
