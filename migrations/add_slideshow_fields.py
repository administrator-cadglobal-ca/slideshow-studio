"""Add name and photo_ids to share_tokens. Idempotent."""
import sqlite3
import sys

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "/var/www/slideshow/instance/slideshow_studio.db"


def column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info('{table}')")
    return any(row[1] == column for row in cur.fetchall())


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if not column_exists(cur, "share_tokens", "name"):
        cur.execute("ALTER TABLE share_tokens ADD COLUMN name VARCHAR(120)")
        print("OK: added name")
    else:
        print("SKIP: name exists")
    if not column_exists(cur, "share_tokens", "photo_ids"):
        cur.execute("ALTER TABLE share_tokens ADD COLUMN photo_ids TEXT")
        print("OK: added photo_ids")
    else:
        print("SKIP: photo_ids exists")
    # Give existing rows a default name
    cur.execute("UPDATE share_tokens SET name='Default' WHERE name IS NULL")
    print(f"OK: set default name on {cur.rowcount} existing rows")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()