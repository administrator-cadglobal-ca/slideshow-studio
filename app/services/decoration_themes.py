"""Decoration themes registry - now reads from DB (themes_v2 tables).

Kept the same public API (get_theme, list_categories, list_themes) for backward
compatibility with events blueprint, preview page, viewer, and MP4 render.
"""
from app import db
from app.models.theme import ThemeCategory, ThemeSubcategory, ThemeV2, ThemeClip
import json


def _clip_to_dict(clip):
    """Serialize a ThemeClip row to a dict matching the old Python format."""
    return {
        "file": clip.file_path,   # includes subcategory or user_uploads path
        "positions": json.loads(clip.positions_json) if clip.positions_json else [],
        "size": clip.size_pct or 10,
        "animate": clip.animation or "twinkle",
        "count": clip.count or 1,
        "position_type": (clip.position_type or "anchor"),
        "freeform": json.loads(clip.freeform_json) if clip.freeform_json else [],
    }


def get_theme(theme_id):
    """Return a theme dict by slug, or None."""
    if not theme_id:
        return None
    theme = db.session.query(ThemeV2).filter_by(slug=theme_id).first()
    if not theme:
        return None
    return {
        "name": theme.name,
        "description": theme.description or "",
        "clips": [_clip_to_dict(c) for c in theme.clips],
        "_subcategory_id": theme.subcategory.slug if theme.subcategory else None,
        "_theme_slug": theme.slug,
    }


def list_categories():
    """Return the full category tree in the old dict format."""
    cats = db.session.query(ThemeCategory).order_by(ThemeCategory.sort_order, ThemeCategory.name).all()
    result = []
    for c in cats:
        cat_out = {
            "id": c.slug,
            "name": c.name,
            "subcategories": [],
        }
        for s in c.subcategories:
            sub_out = {
                "id": s.slug,
                "name": s.name,
                "themes": [
                    {"id": t.slug, "name": t.name, "description": t.description or ""}
                    for t in s.themes
                ],
            }
            cat_out["subcategories"].append(sub_out)
        result.append(cat_out)
    return result


def list_themes():
    """Flat list of all themes."""
    themes = db.session.query(ThemeV2).order_by(ThemeV2.sort_order).all()
    return [{"id": t.slug, "name": t.name, "description": t.description or ""} for t in themes]