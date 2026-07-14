from datetime import datetime, timezone
from app.extensions import db


class Photo(db.Model):
    __tablename__ = "photos"

    id          = db.Column(db.Integer,     primary_key=True)
    project_id  = db.Column(db.String(36),  db.ForeignKey("projects.id"), nullable=False)
    filename    = db.Column(db.String(255),  nullable=False)
    orig_name   = db.Column(db.String(255))
    file_size   = db.Column(db.BigInteger,   default=0)
    width       = db.Column(db.Integer)
    height      = db.Column(db.Integer)
    orientation = db.Column(db.String(10))
    sort_order  = db.Column(db.Integer,      default=0)
    skipped     = db.Column(db.Boolean,      default=False)
    uploaded_at = db.Column(db.DateTime,     default=lambda: datetime.now(timezone.utc))
    note        = db.Column(db.String(200))

    # ── EXIF Date ──────────────────────────────────────────────────────────────
    exif_date        = db.Column(db.DateTime)
    exif_date_str    = db.Column(db.String(30))

    # ── EXIF Camera ────────────────────────────────────────────────────────────
    camera_make      = db.Column(db.String(60))
    camera_model     = db.Column(db.String(80))
    lens_model       = db.Column(db.String(80))
    focal_length     = db.Column(db.String(20))
    focal_length_35  = db.Column(db.String(20))
    aperture         = db.Column(db.String(20))
    shutter_speed    = db.Column(db.String(20))
    iso              = db.Column(db.Integer)
    flash            = db.Column(db.String(40))
    exposure_mode    = db.Column(db.String(40))
    white_balance    = db.Column(db.String(40))
    metering_mode    = db.Column(db.String(40))

    # ── EXIF GPS ────────────────────────────────────────────────────────────────
    gps_lat          = db.Column(db.Float)
    gps_lon          = db.Column(db.Float)
    gps_alt          = db.Column(db.Float)
    gps_speed        = db.Column(db.Float)
    gps_direction    = db.Column(db.Float)
    gps_location     = db.Column(db.String(200))
    gps_place        = db.Column(db.String(80))
    gps_country      = db.Column(db.String(60))

    # ── EXIF Image ─────────────────────────────────────────────────────────────
    color_space      = db.Column(db.String(20))
    software         = db.Column(db.String(80))

    processed_paths  = db.Column(db.Text)
    project          = db.relationship("Project", back_populates="photos")

    @property
    def is_portrait(self):
        if self.width and self.height:
            return self.height > self.width
        return self.orientation == "portrait"

    @property
    def thumbnail_path(self):
        return f"thumb_{self.filename}"

    @property
    def has_note(self):
        return bool(self.note and self.note.strip())

    @property
    def has_gps(self):
        return self.gps_lat is not None and self.gps_lon is not None

    @property
    def gps_maps_url(self):
        if self.has_gps:
            return f"https://maps.google.com/?q={self.gps_lat:.6f},{self.gps_lon:.6f}"
        return ""

    @property
    def camera_display(self):
        parts = []
        if self.camera_make: parts.append(self.camera_make)
        if self.camera_model:
            m = self.camera_model
            if self.camera_make and m.startswith(self.camera_make):
                m = m[len(self.camera_make):].strip()
            parts.append(m)
        return " ".join(parts)

    @property
    def exposure_display(self):
        parts = []
        if self.aperture:        parts.append(self.aperture)
        if self.shutter_speed:   parts.append(f"{self.shutter_speed}s")
        if self.iso:             parts.append(f"ISO {self.iso}")
        if self.focal_length_35: parts.append(self.focal_length_35)
        return "  ·  ".join(parts)

    @property
    def location_display(self):
        return self.gps_location or self.gps_place or ""

    def to_meta_dict(self):
        return {
            "id": self.id, "filename": self.orig_name,
            "width": self.width, "height": self.height,
            "orientation": self.orientation,
            "date": self.exif_date_str or "",
            "camera": self.camera_display,
            "camera_make": self.camera_make or "",
            "camera_model": self.camera_model or "",
            "lens": self.lens_model or "",
            "aperture": self.aperture or "",
            "shutter": self.shutter_speed or "",
            "iso": self.iso,
            "focal_35": self.focal_length_35 or "",
            "exposure": self.exposure_display,
            "flash": self.flash or "",
            "has_gps": self.has_gps,
            "gps_lat": self.gps_lat,
            "gps_lon": self.gps_lon,
            "gps_alt": round(self.gps_alt, 1) if self.gps_alt else None,
            "gps_speed": round(self.gps_speed, 1) if self.gps_speed else None,
            "gps_location": self.gps_location or "",
            "gps_place": self.gps_place or "",
            "gps_country": self.gps_country or "",
            "maps_url": self.gps_maps_url,
            "color_space": self.color_space or "",
            "software": self.software or "",
            "file_size": self.file_size,
        }

    def auto_line2(self, mode: str = "date_location") -> str:
        """
        Generate the automatic second caption line from metadata.
        mode options:
          "date"             → Jun 15, 2026
          "location"         → Banff, AB, Canada
          "date_location"    → Jun 15, 2026  ·  Banff, AB, Canada
          "location_date"    → Banff, AB, Canada  ·  Jun 15, 2026
          "camera"           → Apple iPhone 15 Pro
          "date_camera"      → Jun 15, 2026  ·  Apple iPhone 15 Pro
          "location_camera"  → Banff, AB, Canada  ·  Apple iPhone 15 Pro
          "all"              → Jun 15, 2026  ·  Banff  ·  iPhone 15 Pro
          "none"             → (empty string)
        """
        if not mode or mode == "none":
            return ""

        date     = self.exif_date.strftime("%b %d, %Y") if self.exif_date else ""
        location = self.gps_location or self.gps_place or ""
        camera   = ""
        if self.camera_model:
            m = self.camera_model
            if self.camera_make and m.startswith(self.camera_make):
                m = m[len(self.camera_make):].strip()
            camera = m

        sep = "  ·  "
        parts_map = {
            "date":            [date],
            "location":        [location],
            "date_location":   [date, location],
            "location_date":   [location, date],
            "camera":          [camera],
            "date_camera":     [date, camera],
            "location_camera": [location, camera],
            "all":             [date, location, camera],
        }
        parts = [p for p in parts_map.get(mode, [date, location]) if p]
        return sep.join(parts)

    def __repr__(self):

        return f"<Photo {self.orig_name}>"
