"""Add freeform positioning fields to theme_clips."""
import sqlite3, sys
DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "/var/www/slideshow/instance/slideshow_studio.db"

def col_exists(cur, table, col):
    cur.execute(f"PRAGMA table_info('{table}')")
    return any(r[1] == col for r in cur.fetchall())

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

changes = []
if not col_exists(cur, "theme_clips", "position_type"):
    cur.execute("ALTER TABLE theme_clips ADD COLUMN position_type VARCHAR(20) DEFAULT 'anchor'")
    changes.append("position_type")

if not col_exists(cur, "theme_clips", "freeform_json"):
    # Stores array of {x_pct, y_pct} for freeform positioning
    cur.execute("ALTER TABLE theme_clips ADD COLUMN freeform_json TEXT")
    changes.append("freeform_json")

if changes:
    print("OK: added columns:", ", ".join(changes))
else:
    print("SKIP: all exist")

conn.commit()
conn.close()