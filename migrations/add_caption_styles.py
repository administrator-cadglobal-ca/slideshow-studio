"""Add caption_styles JSON field to share_tokens (nullable, idempotent)."""
import sqlite3
import sys

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "/var/www/slideshow/instance/slideshow_studio.db"


def column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info('{table}')")
    return any(row[1] == column for row in cur.fetchall())


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if not column_exists(cur, "share_tokens", "caption_styles"):
        cur.execute("ALTER TABLE share_tokens ADD COLUMN caption_styles TEXT")
        print("OK: added caption_styles")
    else:
        print("SKIP: caption_styles exists")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()