"""Add decoration_theme to events table."""
import sqlite3, sys
DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "/var/www/slideshow/instance/slideshow_studio.db"

def col_exists(cur, table, col):
    cur.execute(f"PRAGMA table_info('{table}')")
    return any(r[1] == col for r in cur.fetchall())

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
if not col_exists(cur, "events", "decoration_theme"):
    cur.execute("ALTER TABLE events ADD COLUMN decoration_theme VARCHAR(60)")
    print("OK: added decoration_theme")
else:
    print("SKIP: exists")
conn.commit()
conn.close()