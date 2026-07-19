"""Models for theme management (categories -> subcategories -> themes -> clips)."""
from app import db
from datetime import datetime


class ThemeCategory(db.Model):
    __tablename__ = "theme_categories"

    id         = db.Column(db.Integer, primary_key=True)
    slug       = db.Column(db.String(60), unique=True, nullable=False)
    name       = db.Column(db.String(120), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    is_builtin = db.Column(db.Boolean, default=False)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subcategories = db.relationship("ThemeSubcategory", backref="category", lazy="dynamic",
                                     order_by="ThemeSubcategory.sort_order")


class ThemeSubcategory(db.Model):
    __tablename__ = "theme_subcategories"

    id          = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("theme_categories.id"), nullable=False)
    slug        = db.Column(db.String(60), nullable=False)
    name        = db.Column(db.String(120), nullable=False)
    sort_order  = db.Column(db.Integer, default=0)
    is_builtin  = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    themes = db.relationship("ThemeV2", backref="subcategory", lazy="dynamic",
                              order_by="ThemeV2.sort_order")


class ThemeV2(db.Model):
    __tablename__ = "themes_v2"

    id             = db.Column(db.Integer, primary_key=True)
    subcategory_id = db.Column(db.Integer, db.ForeignKey("theme_subcategories.id"), nullable=False)
    slug           = db.Column(db.String(120), unique=True, nullable=False)
    name           = db.Column(db.String(200), nullable=False)
    description    = db.Column(db.Text)
    sort_order     = db.Column(db.Integer, default=0)
    is_builtin     = db.Column(db.Boolean, default=False)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    clips = db.relationship("ThemeClip", backref="theme", lazy="dynamic",
                             order_by="ThemeClip.sort_order",
                             cascade="all, delete-orphan")


class ThemeClip(db.Model):
    __tablename__ = "theme_clips"

    id             = db.Column(db.Integer, primary_key=True)
    theme_id       = db.Column(db.Integer, db.ForeignKey("themes_v2.id"), nullable=False)
    file_path      = db.Column(db.String(300), nullable=False)
    positions_json = db.Column(db.Text, nullable=False)
    size_pct       = db.Column(db.Integer, default=10)
    animation      = db.Column(db.String(60), default="twinkle")
    count          = db.Column(db.Integer, default=1)
    sort_order     = db.Column(db.Integer, default=0)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)