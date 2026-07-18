"""Add render_shares table (idempotent)."""
import sqlite3, sys

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "/var/www/slideshow/instance/slideshow_studio.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS render_shares (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            token          VARCHAR(64) UNIQUE NOT NULL,
            event_id       VARCHAR(36) NOT NULL,
            filename       VARCHAR(255) NOT NULL,
            plain_password VARCHAR(100) NOT NULL DEFAULT 'WELCOME',
            created_by     INTEGER NOT NULL,
            expires_at     DATETIME,
            created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_used_at   DATETIME,
            use_count      INTEGER DEFAULT 0,
            FOREIGN KEY (event_id) REFERENCES events(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_render_shares_token ON render_shares(token)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_render_shares_event_file ON render_shares(event_id, filename)")
    print("OK: render_shares table ready")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()