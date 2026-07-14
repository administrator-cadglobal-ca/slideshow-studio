-- Run once to create tables in Cloudflare D1
-- wrangler d1 execute slideshow-studio-db --file=d1_schema.sql

CREATE TABLE IF NOT EXISTS slideshow_tokens (
    token         TEXT PRIMARY KEY,
    project_id    TEXT NOT NULL,
    user_id       INTEGER NOT NULL,
    project_name  TEXT,
    meta_json     TEXT,       -- frames list, labels, version info
    expires_at    TEXT,       -- ISO datetime or NULL
    use_count     INTEGER DEFAULT 0,
    last_used_at  TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS slideshow_clips (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    token      TEXT NOT NULL,
    label_id   INTEGER NOT NULL,
    label_name TEXT,
    clips_json TEXT NOT NULL,  -- JSON array of clip objects
    FOREIGN KEY (token) REFERENCES slideshow_tokens(token) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tokens_token ON slideshow_tokens(token);
CREATE INDEX IF NOT EXISTS idx_clips_token  ON slideshow_clips(token, label_id);

-- Add password support (run if upgrading existing DB)
ALTER TABLE slideshow_tokens ADD COLUMN password_hash TEXT;
