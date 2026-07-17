"""Idempotently add Photo.caption column. Safe to run multiple times."""
import sqlite3
import sys

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "/var/www/slideshow/instance/slideshow_studio.db"


def column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info('{table}')")
    return any(row[1] == column for row in cur.fetchall())


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        if column_exists(cur, "photos", "caption"):
            print("SKIP: photos.caption already exists")
            return
        cur.execute("ALTER TABLE photos ADD COLUMN caption TEXT")
        conn.commit()
        print("OK: added photos.caption")
    finally:
        conn.close()


if __name__ == "__main__":
    main()