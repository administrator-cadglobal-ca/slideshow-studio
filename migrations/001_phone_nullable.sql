-- Migration 001: Make phone nullable on users and registration_requests
--
-- SQLite does not support ALTER COLUMN, so we rebuild each table.
-- Safe to run multiple times: uses IF NOT EXISTS and IF EXISTS where possible.
--
-- Applied on Hetzner: 2026-07-15
-- Rollback: not supported (would require setting all NULL phones to a fake value first)

BEGIN TRANSACTION;

-- ============================================================================
-- users table: rebuild with phone nullable
-- ============================================================================

CREATE TABLE users_new (
    id              INTEGER PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    phone           VARCHAR(30) UNIQUE,
    role            VARCHAR(20) DEFAULT 'user',
    is_enabled      BOOLEAN DEFAULT 0,
    is_active       BOOLEAN DEFAULT 1,
    discount_code   VARCHAR(50),
    signup_message  TEXT,
    approved_by     INTEGER REFERENCES users(id),
    approved_at     DATETIME,
    quota_bytes     BIGINT DEFAULT 21474836480,
    notify_email    VARCHAR(255),
    google_access_token  TEXT,
    google_refresh_token TEXT,
    google_token_expiry  DATETIME,
    google_email         VARCHAR(255),
    pref_transition  VARCHAR(20) DEFAULT 'fade',
    pref_fps         INTEGER DEFAULT 24,
    pref_title_bg    VARCHAR(10) DEFAULT '#0d1b2a',
    pref_title_color VARCHAR(10) DEFAULT '#ffffff',
    created_at       DATETIME,
    last_login       DATETIME
);

INSERT INTO users_new SELECT * FROM users;
DROP TABLE users;
ALTER TABLE users_new RENAME TO users;

CREATE INDEX ix_users_email ON users(email);

-- ============================================================================
-- registration_requests table: rebuild with phone nullable
-- ============================================================================

CREATE TABLE registration_requests_new (
    id              INTEGER PRIMARY KEY,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(255) NOT NULL,
    phone           VARCHAR(30),
    discount_code   VARCHAR(50),
    message         TEXT,
    status          VARCHAR(20) DEFAULT 'pending',
    reviewed_by     INTEGER REFERENCES users(id),
    reviewed_at     DATETIME,
    review_note     TEXT,
    created_user_id INTEGER REFERENCES users(id),
    created_at      DATETIME
);

INSERT INTO registration_requests_new SELECT * FROM registration_requests;
DROP TABLE registration_requests;
ALTER TABLE registration_requests_new RENAME TO registration_requests;

COMMIT;

-- Verify: both queries should return 1 for the phone column
--   SELECT COUNT(*) FROM pragma_table_info('users') WHERE name='phone' AND "notnull"=0;
--   SELECT COUNT(*) FROM pragma_table_info('registration_requests') WHERE name='phone' AND "notnull"=0;