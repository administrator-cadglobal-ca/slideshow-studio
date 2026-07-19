"""Create theme management tables (idempotent)."""
import sqlite3, sys

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "/var/www/slideshow/instance/slideshow_studio.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS theme_categories (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            slug         VARCHAR(60) UNIQUE NOT NULL,
            name         VARCHAR(120) NOT NULL,
            sort_order   INTEGER DEFAULT 0,
            is_builtin   INTEGER DEFAULT 0,
            user_id      INTEGER,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS theme_subcategories (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id  INTEGER NOT NULL,
            slug         VARCHAR(60) NOT NULL,
            name         VARCHAR(120) NOT NULL,
            sort_order   INTEGER DEFAULT 0,
            is_builtin   INTEGER DEFAULT 0,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category_id, slug),
            FOREIGN KEY (category_id) REFERENCES theme_categories(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS themes_v2 (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            subcategory_id  INTEGER NOT NULL,
            slug            VARCHAR(120) UNIQUE NOT NULL,
            name            VARCHAR(200) NOT NULL,
            description     TEXT,
            sort_order      INTEGER DEFAULT 0,
            is_builtin      INTEGER DEFAULT 0,
            user_id         INTEGER,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subcategory_id) REFERENCES theme_subcategories(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS theme_clips (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            theme_id       INTEGER NOT NULL,
            file_path      VARCHAR(300) NOT NULL,
            positions_json TEXT NOT NULL,
            size_pct       INTEGER DEFAULT 10,
            animation      VARCHAR(60) DEFAULT 'twinkle',
            count          INTEGER DEFAULT 1,
            sort_order     INTEGER DEFAULT 0,
            created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (theme_id) REFERENCES themes_v2(id)
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_tcat_slug ON theme_categories(slug)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tsub_cat ON theme_subcategories(category_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_theme_sub ON themes_v2(subcategory_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_theme_slug ON themes_v2(slug)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_clips_theme ON theme_clips(theme_id)")

    print("OK: theme tables ready")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()