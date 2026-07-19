"""Seed DB with existing decoration_themes.py themes (idempotent).

Run: python migrations/seed_theme_data.py [db_path]
"""
import sqlite3, sys, json, os

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "/var/www/slideshow/instance/slideshow_studio.db"

# Import CATEGORIES from decoration_themes.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app.services.decoration_themes import CATEGORIES


def slugify(text):
    import re
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text[:60] or "item"


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cat_sort_order = 0
    added_cats = added_subs = added_themes = added_clips = 0

    for cat_slug, cat_data in CATEGORIES.items():
        cat_name = cat_data["name"]
        cur.execute("SELECT id FROM theme_categories WHERE slug=?", (cat_slug,))
        row = cur.fetchone()
        if row:
            cat_id = row[0]
        else:
            cur.execute(
                "INSERT INTO theme_categories (slug, name, sort_order, is_builtin) VALUES (?, ?, ?, 1)",
                (cat_slug, cat_name, cat_sort_order),
            )
            cat_id = cur.lastrowid
            added_cats += 1
        cat_sort_order += 1

        sub_sort_order = 0
        for sub_slug, sub_data in cat_data["subcategories"].items():
            sub_name = sub_data["name"]
            cur.execute(
                "SELECT id FROM theme_subcategories WHERE category_id=? AND slug=?",
                (cat_id, sub_slug),
            )
            row = cur.fetchone()
            if row:
                sub_id = row[0]
            else:
                cur.execute(
                    "INSERT INTO theme_subcategories (category_id, slug, name, sort_order, is_builtin) VALUES (?, ?, ?, ?, 1)",
                    (cat_id, sub_slug, sub_name, sub_sort_order),
                )
                sub_id = cur.lastrowid
                added_subs += 1
            sub_sort_order += 1

            theme_sort_order = 0
            for theme_slug, theme_data in sub_data["themes"].items():
                cur.execute("SELECT id FROM themes_v2 WHERE slug=?", (theme_slug,))
                row = cur.fetchone()
                if row:
                    theme_id = row[0]
                else:
                    cur.execute(
                        "INSERT INTO themes_v2 (subcategory_id, slug, name, description, sort_order, is_builtin) VALUES (?, ?, ?, ?, ?, 1)",
                        (sub_id, theme_slug, theme_data["name"],
                         theme_data.get("description", ""), theme_sort_order),
                    )
                    theme_id = cur.lastrowid
                    added_themes += 1
                theme_sort_order += 1

                # Clips
                cur.execute("SELECT COUNT(*) FROM theme_clips WHERE theme_id=?", (theme_id,))
                if cur.fetchone()[0] == 0:
                    clip_sort_order = 0
                    for clip in theme_data.get("clips", []):
                        # Path: <subcategory_slug>/<file>
                        file_path = f"{sub_slug}/{clip['file']}"
                        cur.execute(
                            "INSERT INTO theme_clips (theme_id, file_path, positions_json, size_pct, animation, count, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (theme_id, file_path, json.dumps(clip["positions"]),
                             clip.get("size", 10), clip.get("animate", "twinkle"),
                             clip.get("count", 1), clip_sort_order),
                        )
                        added_clips += 1
                        clip_sort_order += 1

    conn.commit()
    conn.close()
    print(f"OK: added {added_cats} categories, {added_subs} subcategories, {added_themes} themes, {added_clips} clips")


if __name__ == "__main__":
    main()