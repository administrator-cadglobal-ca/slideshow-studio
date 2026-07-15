# 03 — Migration Plan

How to migrate 22 templates without breaking the live app during the transition.

---

## Strategy: strangler fig

Coined by Martin Fowler for legacy replacements. New code grows around the old until the old can be removed. Applied here:

1. Ship the new base template + design system infrastructure **first**, without changing any page templates. Every existing page keeps working, just with new fonts and slightly different chrome.
2. Migrate templates **one at a time**, in dependency order.
3. Each migrated template is behind no feature flag — once it's better than the old one, it replaces it directly.
4. Rollback plan: git revert. No database migrations that can't be rolled back.

**Why not a feature flag?** For a template rebuild, the visual difference is obvious enough that a "gradual rollout" doesn't help. And feature flags add complexity you'll never remove. Trust the design system and ship.

---

## Migration order (priority)

### Wave 1 — Foundation (1 session)

Not migrating templates yet — building the ground everything sits on.

| # | File | Change type |
|---|---|---|
| 1 | `app/static/css/input.css` | New — Tailwind entry point |
| 2 | `tailwind.config.js` | New — design tokens |
| 3 | `app/static/js/htmx.min.js` | New — 14KB self-hosted |
| 4 | `app/static/js/alpine.min.js` | New — 15KB self-hosted |
| 5 | `app/static/fonts/InterTight-Variable.woff2` | New |
| 6 | `app/static/fonts/JetBrainsMono-Variable.woff2` | New |
| 7 | `app/templates/shared/base.html` | Replaced |
| 8 | `app/templates/shared/_bottom_nav.html` | New |
| 9 | `app/templates/shared/_desktop_sidebar.html` | New |
| 10 | `app/templates/shared/_header.html` | New |
| 11 | `app/templates/shared/_flash.html` | New |
| 12 | `deploy/deploy.sh` | Add `tailwindcss` build step |

**Verification after wave 1:** Every existing page loads. May look slightly different (new fonts, new base chrome) but is functionally identical.

### Wave 2 — Auth (must work before anything else) (1 session)

Nobody uses the app if they can't log in.

| # | Template | Complexity |
|---|---|---|
| 13 | `auth/login.html` | Medium — email input, OTP request |
| 14 | `auth/verify.html` | Medium — 8-char OTP input, resend |
| 15 | `auth/register.html` | Medium — email + phone + name + signup message |
| 16 | `auth/register_done.html` | Simple — "waiting for approval" state |

Special attention: OTP input needs auto-focus, paste handling, mobile keyboard type (`inputmode="text"` with `autocapitalize="characters"`), and shouldn't allow lowercase input at all.

### Wave 3 — Dashboard & Profile (1 session)

The pages users hit on every login.

| # | Template | Complexity |
|---|---|---|
| 17 | `dashboard/index.html` | High — hub page, needs empty state, recent projects, storage summary, "next action" CTA |
| 18 | `dashboard/profile.html` | Medium — user's own profile edit; preferences (transitions, fps, colors) |

Special attention: dashboard is where new users land after approval. First-run empty state must guide them to create their first project.

### Wave 4 — Projects (2 sessions)

The core value of the app. Five templates.

| # | Template | Complexity |
|---|---|---|
| 19 | `projects/index.html` | High — grid of project cards, mobile-first, with filter/sort |
| 20 | `projects/new.html` | Medium — create form, template picker |
| 21 | `projects/show.html` | Very high — main workspace, photo grid, drag-reorder, batch operations |
| 22 | `projects/settings.html` | Medium — per-project config |
| 23 | `projects/notes.html` | Simple — text notes attached to project |
| 24 | `projects/preview.html` | High — player-like preview of the slideshow before render |

Split across two sessions:
- Session 1: index, new, settings, notes (simpler group)
- Session 2: show, preview (hardest — photo grid + drag-reorder + preview player)

### Wave 5 — Renders (1 session)

Where users export MP4s.

| # | Template | Complexity |
|---|---|---|
| 25 | `renders/index.html` | Medium — list of past renders + statuses |
| 26 | `renders/show.html` | High — active render progress, download UI, error display |

Special attention: real-time updates for in-progress renders. Use HTMX polling with `hx-trigger="every 3s"` while status is `rendering`, stop polling on terminal state.

### Wave 6 — Audio Library (1 session)

Music/clip management for slideshows.

| # | Template | Complexity |
|---|---|---|
| 27 | `audio/index.html` | Medium — grid of audio files |
| 28 | `audio/clips.html` | Medium — clips list |
| 29 | `audio/clip_editor.html` | Very high — waveform editor, trim controls |
| 30 | `audio/labels.html` | Simple — tag management |

The clip_editor is the most complex non-admin screen in the app. Waveform display works fine on mobile with pinch-zoom, but the trim UX needs care.

### Wave 7 — Admin (1 session — this bundle's pilot)

Already spec'd in detail in `02_USERS_ADMIN_SPEC.md`.

| # | Template | Complexity |
|---|---|---|
| 31 | `admin/index.html` | Medium — dashboard with stats, pending requests, audit log summary |
| 32 | `admin/requests.html` | Medium — pending signup approvals (can be merged into users?) |
| 33 | `admin/users.html` | Very high — the pilot |

**Question to resolve:** does `admin/requests.html` still need to exist as a separate template, or can the "Pending" filter chip on `admin/users.html` replace it? Recommendation: merge. Fewer distinct pages = fewer places for admin actions to live.

### Wave 8 — Share (1 session)

Public-facing player view (shared slideshow links).

| # | Template | Complexity |
|---|---|---|
| 34 | `share/player.html` | High — public share page, no auth, video/slideshow player |

Special attention: this is the only public-facing page in the app. Design language should feel warm and celebratory — this is where a family member sees the finished work. Slightly different aesthetic from admin pages (more airy, more the-photo-is-the-star).

---

## Total effort estimate

**8 waves × 1-2 sessions each = 10-14 focused sessions.**

At 2-3 hours per session, that's 20-40 hours of work. Realistic timeline: 3-6 weeks of part-time evenings.

Wave 1 (foundation) is the highest-value first move. Ships without touching any user-facing template, but makes every subsequent wave 2-3x faster because the components are already there.

---

## Schema migrations

Any wave that requires new columns or tables. Applied via a plain SQL migration file, executed by hand or by a lightweight migration runner (Alembic if you want it, or just a `migrations/` folder with numbered `.sql` files).

### Migration 001 — Add user status columns (Wave 7)

```sql
-- migrations/001_user_status_columns.up.sql
ALTER TABLE users ADD COLUMN suspended_at DATETIME;
ALTER TABLE users ADD COLUMN suspended_by INTEGER REFERENCES users(id);
ALTER TABLE users ADD COLUMN suspension_reason VARCHAR(500);
ALTER TABLE users ADD COLUMN deactivated_at DATETIME;
ALTER TABLE users ADD COLUMN deactivated_by INTEGER REFERENCES users(id);
ALTER TABLE users ADD COLUMN storage_used_bytes BIGINT DEFAULT 0;
ALTER TABLE users ADD COLUMN last_login_ip VARCHAR(45);
ALTER TABLE users ADD COLUMN last_login_user_agent VARCHAR(500);
ALTER TABLE users ADD COLUMN email_verified_at DATETIME;
ALTER TABLE users ADD COLUMN phone_verified_at DATETIME;
ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500);
ALTER TABLE users ADD COLUMN admin_notes TEXT;
```

Rollback:
```sql
-- migrations/001_user_status_columns.down.sql
-- SQLite can't DROP COLUMN directly, requires recreate. Skip rollback for these.
-- All new columns are nullable, so safe to leave in place if reverting app code.
```

**Note on SQLite:** dropping columns requires table recreation. For this app's scale, leave rollback empty — the columns are nullable and unused columns are cheap. Only issue would be storage overhead, negligible.

### Migration 002 — Admin audit log (Wave 7)

```sql
-- migrations/002_admin_audit_log.up.sql
CREATE TABLE admin_audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user_id   INTEGER NOT NULL REFERENCES users(id),
    target_user_id  INTEGER REFERENCES users(id),
    target_type     VARCHAR(50) NOT NULL,
    action          VARCHAR(50) NOT NULL,
    payload_json    TEXT,
    ip              VARCHAR(45),
    user_agent      VARCHAR(500),
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_audit_target ON admin_audit_log(target_type, target_user_id);
CREATE INDEX ix_audit_admin ON admin_audit_log(admin_user_id, created_at);
```

Rollback: `DROP TABLE admin_audit_log; DROP INDEX ix_audit_target; DROP INDEX ix_audit_admin;`

### Applying migrations

Add a bash script `deploy/apply_migrations.sh`:

```bash
#!/bin/bash
set -e
DB=/var/www/slideshow/instance/slideshow_studio.db
MIGRATIONS_DIR=/var/www/slideshow/migrations

# Track applied migrations in a table
sqlite3 "$DB" "CREATE TABLE IF NOT EXISTS schema_migrations (id TEXT PRIMARY KEY, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP);"

for f in "$MIGRATIONS_DIR"/*.up.sql; do
    name=$(basename "$f" .up.sql)
    exists=$(sqlite3 "$DB" "SELECT 1 FROM schema_migrations WHERE id = '$name';")
    if [ -z "$exists" ]; then
        echo "Applying $name..."
        sqlite3 "$DB" < "$f"
        sqlite3 "$DB" "INSERT INTO schema_migrations (id) VALUES ('$name');"
    fi
done
```

Called from `deploy/deploy.sh` after `pip install`, before `systemctl restart slideshow`.

---

## Risk mitigation

**Zero-downtime deploys:** already the case — systemd `Restart=always`, gunicorn takes ~2s to restart. Users see one refresh with a slower response, then normal.

**Backup before migration:** already have `/root/x4d-backup.sh` on cron. Manual snapshot before each wave:

```bash
cp /var/www/slideshow/instance/slideshow_studio.db \
   /var/www/slideshow/instance/backup_$(date +%Y%m%d_%H%M).db
```

**Rollback playbook per wave:**
1. `git revert <commit-range>` in the repo
2. `git pull` on Hetzner
3. `bash deploy/deploy.sh` — re-runs Tailwind build, pip install (no-op), restart
4. Total downtime: <10 seconds

**If a schema migration goes bad:** restore the pre-migration `.db` backup:
```bash
systemctl stop slideshow
cp /var/www/slideshow/instance/backup_YYYYMMDD_HHMM.db \
   /var/www/slideshow/instance/slideshow_studio.db
systemctl start slideshow
```

---

## Verification checklist per wave

At the end of every wave:

1. ✅ All previous waves still work (regression check)
2. ✅ The new wave's screens work at 375px, 768px, 1024px, 1440px
3. ✅ Dark mode works on the new screens
4. ✅ Keyboard navigation works
5. ✅ Screen reader announces state changes (test with VoiceOver on iOS or NVDA on Windows)
6. ✅ HTMX partial responses don't break when the main page is reloaded
7. ✅ Error responses (4xx/5xx) are handled gracefully
8. ✅ Empty states render correctly (delete all users temporarily to verify)
9. ✅ Loading skeletons appear on slow responses (simulate with `hx-trigger="load delay:2s"`)
10. ✅ Bundle size: check `app.css` is still <30KB gzipped after new templates added
