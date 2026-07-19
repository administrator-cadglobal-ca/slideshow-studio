"""Themes management blueprint - CRUD for categories, subcategories, themes, clips."""
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.theme import ThemeCategory, ThemeSubcategory, ThemeV2, ThemeClip
import json
import os
import re
import uuid

bp = Blueprint("themes", __name__)

ALLOWED_CLIP_EXTS = {".svg", ".png", ".jpg", ".jpeg", ".gif"}


def _slugify(text):
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text[:60] or "item"


def _unique_slug(text, model, field="slug", **filters):
    """Generate a slug unique to the model (optionally filtered)."""
    base = _slugify(text)
    slug = base
    counter = 2
    while True:
        q = db.session.query(model).filter(getattr(model, field) == slug)
        for k, v in filters.items():
            q = q.filter(getattr(model, k) == v)
        if not q.first():
            return slug
        slug = f"{base}-{counter}"
        counter += 1


# ── Themes management page ─────────────────────────────────────────────────
@bp.route("/")
@login_required
def index():
    return render_template("themes/index.html", is_themes_view=True)


# ── Categories ──────────────────────────────────────────────────────────────
@bp.route("/api/categories", methods=["GET"])
@login_required
def list_categories():
    cats = db.session.query(ThemeCategory).order_by(ThemeCategory.sort_order, ThemeCategory.name).all()
    return jsonify({
        "categories": [
            {
                "id": c.id,
                "slug": c.slug,
                "name": c.name,
                "sort_order": c.sort_order,
                "is_builtin": bool(c.is_builtin),
                "subcategory_count": c.subcategories.count(),
            }
            for c in cats
        ]
    })


@bp.route("/api/categories", methods=["POST"])
@login_required
def create_category():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    slug = _unique_slug(name, ThemeCategory)
    cat = ThemeCategory(
        slug=slug, name=name,
        sort_order=int(data.get("sort_order") or 0),
        user_id=current_user.id,
    )
    db.session.add(cat)
    db.session.commit()
    return jsonify({"ok": True, "id": cat.id, "slug": cat.slug})


@bp.route("/api/categories/<int:cat_id>", methods=["PATCH"])
@login_required
def update_category(cat_id):
    cat = db.session.get(ThemeCategory, cat_id)
    if not cat:
        return jsonify({"error": "not found"}), 404
    data = request.json or {}
    if "name" in data:
        cat.name = data["name"].strip()
    if "sort_order" in data:
        cat.sort_order = int(data["sort_order"] or 0)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/categories/<int:cat_id>", methods=["DELETE"])
@login_required
def delete_category(cat_id):
    cat = db.session.get(ThemeCategory, cat_id)
    if not cat:
        return jsonify({"error": "not found"}), 404
    if cat.is_builtin:
        return jsonify({"error": "cannot delete built-in category"}), 400
    # Cascade delete: subcategories, themes, clips
    for sub in cat.subcategories:
        for theme in sub.themes:
            db.session.delete(theme)
        db.session.delete(sub)
    db.session.delete(cat)
    db.session.commit()
    return jsonify({"ok": True})


# ── Subcategories ───────────────────────────────────────────────────────────
@bp.route("/api/categories/<int:cat_id>/subcategories", methods=["GET"])
@login_required
def list_subcategories(cat_id):
    subs = db.session.query(ThemeSubcategory).filter_by(category_id=cat_id)\
              .order_by(ThemeSubcategory.sort_order).all()
    return jsonify({
        "subcategories": [
            {"id": s.id, "slug": s.slug, "name": s.name, "sort_order": s.sort_order,
             "is_builtin": bool(s.is_builtin), "theme_count": s.themes.count()}
            for s in subs
        ]
    })


@bp.route("/api/categories/<int:cat_id>/subcategories", methods=["POST"])
@login_required
def create_subcategory(cat_id):
    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    slug = _unique_slug(name, ThemeSubcategory, category_id=cat_id)
    sub = ThemeSubcategory(
        category_id=cat_id, slug=slug, name=name,
        sort_order=int(data.get("sort_order") or 0),
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify({"ok": True, "id": sub.id, "slug": sub.slug})


@bp.route("/api/subcategories/<int:sub_id>", methods=["PATCH"])
@login_required
def update_subcategory(sub_id):
    sub = db.session.get(ThemeSubcategory, sub_id)
    if not sub:
        return jsonify({"error": "not found"}), 404
    data = request.json or {}
    if "name" in data:
        sub.name = data["name"].strip()
    if "sort_order" in data:
        sub.sort_order = int(data["sort_order"] or 0)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/subcategories/<int:sub_id>", methods=["DELETE"])
@login_required
def delete_subcategory(sub_id):
    sub = db.session.get(ThemeSubcategory, sub_id)
    if not sub:
        return jsonify({"error": "not found"}), 404
    if sub.is_builtin:
        return jsonify({"error": "cannot delete built-in subcategory"}), 400
    for theme in sub.themes:
        db.session.delete(theme)
    db.session.delete(sub)
    db.session.commit()
    return jsonify({"ok": True})


# ── Themes ──────────────────────────────────────────────────────────────────
@bp.route("/api/subcategories/<int:sub_id>/themes", methods=["GET"])
@login_required
def list_themes(sub_id):
    themes = db.session.query(ThemeV2).filter_by(subcategory_id=sub_id)\
                .order_by(ThemeV2.sort_order).all()
    return jsonify({
        "themes": [
            {"id": t.id, "slug": t.slug, "name": t.name, "description": t.description,
             "sort_order": t.sort_order, "is_builtin": bool(t.is_builtin),
             "clip_count": t.clips.count()}
            for t in themes
        ]
    })


@bp.route("/api/subcategories/<int:sub_id>/themes", methods=["POST"])
@login_required
def create_theme(sub_id):
    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    slug = _unique_slug(name, ThemeV2)
    theme = ThemeV2(
        subcategory_id=sub_id, slug=slug, name=name,
        description=data.get("description", ""),
        sort_order=int(data.get("sort_order") or 0),
        user_id=current_user.id,
    )
    db.session.add(theme)
    db.session.commit()
    return jsonify({"ok": True, "id": theme.id, "slug": theme.slug})


@bp.route("/api/themes/<int:theme_id>", methods=["GET"])
@login_required
def get_theme(theme_id):
    theme = db.session.get(ThemeV2, theme_id)
    if not theme:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "id": theme.id, "slug": theme.slug, "name": theme.name,
        "description": theme.description, "is_builtin": bool(theme.is_builtin),
        "clips": [
            {"id": c.id, "file_path": c.file_path,
             "positions": json.loads(c.positions_json) if c.positions_json else [],
             "size_pct": c.size_pct, "animation": c.animation, "count": c.count,
             "sort_order": c.sort_order}
            for c in theme.clips
        ]
    })


@bp.route("/api/themes/<int:theme_id>", methods=["PATCH"])
@login_required
def update_theme(theme_id):
    theme = db.session.get(ThemeV2, theme_id)
    if not theme:
        return jsonify({"error": "not found"}), 404
    data = request.json or {}
    if "name" in data:
        theme.name = data["name"].strip()
    if "description" in data:
        theme.description = data["description"]
    if "sort_order" in data:
        theme.sort_order = int(data["sort_order"] or 0)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/themes/<int:theme_id>", methods=["DELETE"])
@login_required
def delete_theme(theme_id):
    theme = db.session.get(ThemeV2, theme_id)
    if not theme:
        return jsonify({"error": "not found"}), 404
    if theme.is_builtin:
        return jsonify({"error": "cannot delete built-in theme"}), 400
    db.session.delete(theme)
    db.session.commit()
    return jsonify({"ok": True})


# ── Clips (upload + manage) ────────────────────────────────────────────────
@bp.route("/api/themes/<int:theme_id>/clips", methods=["POST"])
@login_required
def upload_clip(theme_id):
    theme = db.session.get(ThemeV2, theme_id)
    if not theme:
        return jsonify({"error": "not found"}), 404

    f = request.files.get("file")
    if not f:
        return jsonify({"error": "no file"}), 400

    orig_name = secure_filename(f.filename or "")
    ext = os.path.splitext(orig_name)[1].lower()
    if ext not in ALLOWED_CLIP_EXTS:
        return jsonify({"error": f"only {', '.join(ALLOWED_CLIP_EXTS)} allowed"}), 400

    # Save to /app/static/clips/user_uploads/<theme_slug>/<uuid>.<ext>
    upload_dir = os.path.join(current_app.root_path, "static", "clips", "user_uploads", theme.slug)
    os.makedirs(upload_dir, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex[:8]}_{orig_name}"
    dest = os.path.join(upload_dir, unique_name)
    f.save(dest)

    file_path = f"user_uploads/{theme.slug}/{unique_name}"

    positions = request.form.get("positions", "top-left")
    positions_list = [p.strip() for p in positions.split(",") if p.strip()]

    max_order = db.session.query(db.func.coalesce(db.func.max(ThemeClip.sort_order), 0))\
                  .filter_by(theme_id=theme_id).scalar() or 0

    clip = ThemeClip(
        theme_id=theme_id,
        file_path=file_path,
        positions_json=json.dumps(positions_list),
        size_pct=int(request.form.get("size_pct", 10) or 10),
        animation=request.form.get("animation", "twinkle"),
        count=int(request.form.get("count", 1) or 1),
        sort_order=max_order + 1,
    )
    db.session.add(clip)
    db.session.commit()

    return jsonify({"ok": True, "id": clip.id, "file_path": file_path})


@bp.route("/api/clips/<int:clip_id>", methods=["PATCH"])
@login_required
def update_clip(clip_id):
    clip = db.session.get(ThemeClip, clip_id)
    if not clip:
        return jsonify({"error": "not found"}), 404
    data = request.json or {}
    if "positions" in data:
        clip.positions_json = json.dumps(data["positions"])
    if "size_pct" in data:
        clip.size_pct = int(data["size_pct"] or 10)
    if "animation" in data:
        clip.animation = data["animation"]
    if "count" in data:
        clip.count = int(data["count"] or 1)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/clips/<int:clip_id>", methods=["DELETE"])
@login_required
def delete_clip(clip_id):
    clip = db.session.get(ThemeClip, clip_id)
    if not clip:
        return jsonify({"error": "not found"}), 404
    # Try to delete the file too
    try:
        full = os.path.join(current_app.root_path, "static", "clips", clip.file_path)
        if os.path.exists(full):
            os.unlink(full)
    except Exception:
        pass
    db.session.delete(clip)
    db.session.commit()
    return jsonify({"ok": True})


# ── Iconify API integration ─────────────────────────────────────────────────
@bp.route("/api/iconify/search", methods=["GET"])
@login_required
def iconify_search():
    """Proxy search to Iconify public API to find open-source icons."""
    import requests
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "query required"}), 400

    limit = min(int(request.args.get("limit", 32) or 32), 64)
    try:
        r = requests.get(
            f"https://api.iconify.design/search",
            params={"query": query, "limit": limit},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        # Return icons in a friendly format
        icons = data.get("icons", [])  # ["prefix:name", ...]
        results = []
        for icon_ref in icons:
            if ":" not in icon_ref:
                continue
            prefix, name = icon_ref.split(":", 1)
            results.append({
                "id": icon_ref,
                "prefix": prefix,
                "name": name,
                "preview_url": f"https://api.iconify.design/{prefix}/{name}.svg?height=64",
            })
        return jsonify({"icons": results, "total": data.get("total", len(results))})
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500


@bp.route("/api/themes/<int:theme_id>/import-iconify", methods=["POST"])
@login_required
def import_iconify_icon(theme_id):
    """Download an Iconify icon and add it as a clip to the theme."""
    import requests
    theme = db.session.get(ThemeV2, theme_id)
    if not theme:
        return jsonify({"error": "not found"}), 404

    data = request.json or {}
    icon_id = data.get("icon_id", "")  # e.g. "mdi:balloon"
    if ":" not in icon_id:
        return jsonify({"error": "invalid icon_id"}), 400

    prefix, name = icon_id.split(":", 1)
    # Fetch SVG - allow color customization
    color = data.get("color", "")
    params = {}
    if color:
        params["color"] = color

    # Request at 64px size (default is 24, too small)
    if "height" not in params:
        params["height"] = "64"
    try:
        r = requests.get(f"https://api.iconify.design/{prefix}/{name}.svg", params=params, timeout=10)
        r.raise_for_status()
        svg_content = r.text
    except Exception as e:
        return jsonify({"error": f"fetch failed: {e}"}), 500

    # Save to uploads
    upload_dir = os.path.join(current_app.root_path, "static", "clips", "user_uploads", theme.slug)
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = f"iconify_{prefix}_{name}.svg".replace("/", "_")
    dest_path = os.path.join(upload_dir, safe_name)
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    file_path = f"user_uploads/{theme.slug}/{safe_name}"
    positions = data.get("positions") or ["top-left", "top-right"]

    max_order = db.session.query(db.func.coalesce(db.func.max(ThemeClip.sort_order), 0))\
                  .filter_by(theme_id=theme_id).scalar() or 0
    clip = ThemeClip(
        theme_id=theme_id,
        file_path=file_path,
        positions_json=json.dumps(positions),
        size_pct=int(data.get("size_pct", 10) or 10),
        animation=data.get("animation", "twinkle"),
        count=int(data.get("count", 2) or 2),
        sort_order=max_order + 1,
    )
    db.session.add(clip)
    db.session.commit()

    return jsonify({"ok": True, "id": clip.id, "file_path": file_path})


# ── Full tree for use by preview/render/viewer ─────────────────────────────
@bp.route("/api/tree", methods=["GET"])
@login_required
def get_tree():
    """Return the full categories tree with themes and clips for consumption."""
    cats = db.session.query(ThemeCategory).order_by(ThemeCategory.sort_order).all()
    result = []
    for c in cats:
        cat_out = {"id": c.id, "slug": c.slug, "name": c.name, "subcategories": []}
        for s in c.subcategories:
            sub_out = {"id": s.id, "slug": s.slug, "name": s.name, "themes": []}
            for t in s.themes:
                theme_out = {
                    "id": t.id, "slug": t.slug, "name": t.name,
                    "description": t.description,
                    "clips": [
                        {"file_path": cl.file_path,
                         "positions": json.loads(cl.positions_json) if cl.positions_json else [],
                         "size_pct": cl.size_pct, "animation": cl.animation,
                         "count": cl.count}
                        for cl in t.clips
                    ],
                }
                sub_out["themes"].append(theme_out)
            cat_out["subcategories"].append(sub_out)
        result.append(cat_out)
    return jsonify({"categories": result})