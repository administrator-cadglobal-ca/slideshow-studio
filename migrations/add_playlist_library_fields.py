"""Add library_id + is_default columns to playlists (nullable, idempotent)."""
import sqlite3, sys
DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "/var/www/slideshow/instance/slideshow_studio.db"

def col_exists(cur, table, col):
    cur.execute(f"PRAGMA table_info('{table}')")
    return any(r[1] == col for r in cur.fetchall())

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

changes = []
if not col_exists(cur, "playlists", "library_id"):
    cur.execute("ALTER TABLE playlists ADD COLUMN library_id INTEGER REFERENCES libraries(id)")
    changes.append("library_id")

if not col_exists(cur, "playlists", "is_default"):
    cur.execute("ALTER TABLE playlists ADD COLUMN is_default INTEGER DEFAULT 0")
    changes.append("is_default")

if changes:
    print("OK: added columns:", ", ".join(changes))
else:
    print("SKIP: all exist")

conn.commit()
conn.close()