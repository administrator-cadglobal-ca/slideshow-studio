# 05 — Routes Inventory

Snapshot of what each blueprint does today, inferred from template names. Confirms scope of the rebuild.

Blueprints found at `/var/www/slideshow/app/blueprints/`:

- `admin.py`
- `api.py`
- `audio.py`
- `auth.py`
- `dashboard.py`
- `projects.py`
- `renders.py`
- `share.py`

Templates found at `/var/www/slideshow/app/templates/`:

- `admin/` (index, requests, users)
- `audio/` (clip_editor, clips, index, labels)
- `auth/` (login, register, register_done, verify)
- `dashboard/` (index, profile)
- `projects/` (index, new, notes, preview, settings, show)
- `renders/` (index, show)
- `share/` (player)
- `shared/` (base) — layout only

---

## Inferred URL map

### `auth.py` — Login, signup, OTP verify

| Method | URL | Template | Purpose |
|---|---|---|---|
| GET | `/auth/login` | `auth/login.html` | Email entry form |
| POST | `/auth/login` | (redirects) | Submit email → generate OTP → redirect to verify |
| GET | `/auth/verify` | `auth/verify.html` | OTP entry form |
| POST | `/auth/verify` | (redirects) | Submit OTP → validate → log in → redirect to `/` |
| POST | `/auth/verify/resend` | (partial) | Resend OTP |
| GET | `/auth/register` | `auth/register.html` | Signup form |
| POST | `/auth/register` | (redirects) | Submit signup → create user record with `is_enabled=False` → redirect to done |
| GET | `/auth/register_done` | `auth/register_done.html` | "Waiting for approval" page |
| GET | `/auth/logout` | (redirects) | Log out, redirect to login |

### `dashboard.py` — User's home & profile

| Method | URL | Template | Purpose |
|---|---|---|---|
| GET | `/` or `/dashboard` | `dashboard/index.html` | Landing page after login |
| GET | `/profile` | `dashboard/profile.html` | User's own profile |
| POST | `/profile` | (partial) | Update profile fields |

### `projects.py` — Slideshow projects

| Method | URL | Template | Purpose |
|---|---|---|---|
| GET | `/projects` | `projects/index.html` | List of user's projects |
| GET | `/projects/new` | `projects/new.html` | Create form |
| POST | `/projects/new` | (redirect) | Create project |
| GET | `/projects/<id>` | `projects/show.html` | Main workspace |
| GET | `/projects/<id>/settings` | `projects/settings.html` | Per-project config |
| POST | `/projects/<id>/settings` | (partial) | Update settings |
| GET | `/projects/<id>/notes` | `projects/notes.html` | Notes editor |
| POST | `/projects/<id>/notes` | (partial) | Save notes |
| GET | `/projects/<id>/preview` | `projects/preview.html` | In-browser slideshow preview |
| POST | `/projects/<id>/photos/upload` | (partial) | Photo upload endpoint |
| POST | `/projects/<id>/photos/<pid>/reorder` | (partial) | Change photo order |
| DELETE | `/projects/<id>/photos/<pid>` | (partial) | Delete photo |
| DELETE | `/projects/<id>` | (redirect) | Delete project |

### `renders.py` — MP4 exports

| Method | URL | Template | Purpose |
|---|---|---|---|
| GET | `/renders` | `renders/index.html` | List of user's renders |
| POST | `/projects/<id>/render` | (redirect) | Kick off render, redirect to renders/show |
| GET | `/renders/<id>` | `renders/show.html` | Individual render status/download |
| GET | `/renders/<id>/status.partial` | (partial) | HTMX polling endpoint for progress |
| GET | `/renders/<id>/download` | (file stream) | Serve MP4 or redirect to R2 pre-signed URL |

### `audio.py` — Audio library

| Method | URL | Template | Purpose |
|---|---|---|---|
| GET | `/audio` | `audio/index.html` | Uploaded audio files |
| POST | `/audio/upload` | (partial) | Upload new audio |
| DELETE | `/audio/<id>` | (partial) | Delete audio |
| GET | `/audio/clips` | `audio/clips.html` | Clips derived from source files |
| GET | `/audio/clips/<id>/edit` | `audio/clip_editor.html` | Trim / edit a clip |
| POST | `/audio/clips/<id>/edit` | (redirect) | Save clip changes |
| GET | `/audio/labels` | `audio/labels.html` | Manage tags |
| POST | `/audio/labels` | (partial) | Add/remove tags |

### `share.py` — Public share links

| Method | URL | Template | Purpose |
|---|---|---|---|
| GET | `/share/<token>` | `share/player.html` | Public share view (no auth) |
| GET | `/share/<token>/media/<path>` | (file stream) | Serve share-linked media |

### `admin.py` — Administration

| Method | URL | Template | Purpose |
|---|---|---|---|
| GET | `/admin` | `admin/index.html` | Admin dashboard |
| GET | `/admin/requests` | `admin/requests.html` | Pending signup approvals (may be merged into users) |
| POST | `/admin/requests/<id>/approve` | (partial) | Approve pending user |
| POST | `/admin/requests/<id>/reject` | (partial) | Reject pending user |
| GET | `/admin/users` | `admin/users.html` | Users list |
| GET | `/admin/users/<id>` | (bottom sheet / side panel) | User detail |
| POST | `/admin/users/<id>/*` | (partials) | All admin user actions (see spec) |

### `api.py` — Programmatic / AJAX endpoints

Purpose unclear from templates (no templates in `api/`). Possibly:
- Photo upload API (multipart, JSON response)
- Audio processing callbacks
- Health check endpoint (`/api/health`)
- Metrics endpoint

Needs source read to confirm. Not affecting rebuild — API endpoints stay as-is.

---

## Migration-relevant observations

**Blueprints stay as-is.** No routing changes needed. The rebuild only replaces templates and adds HTMX-specific partial endpoints.

**HTMX partial endpoints are new.** For each template that has interactive state (approve buttons, form saves, filter updates), add a `*.partial` route that returns just the fragment. Naming convention: append `/partial` or `/status.partial` to the base route.

**No new blueprints needed.** All new admin actions fit within `admin.py`. All new project interactions fit within `projects.py`.

**One blueprint may split:** `admin.py` may grow large. Consider splitting into `admin/users.py`, `admin/requests.py`, `admin/audit.py` after Wave 7 if it exceeds ~500 lines.

---

## Confirming this inventory

To verify these guesses match reality, next session should start by dumping the actual routes:

```bash
cd /var/www/slideshow
source venv/bin/activate
python -c "
from run import app
for rule in app.url_map.iter_rules():
    methods = ','.join(m for m in rule.methods if m not in ('HEAD', 'OPTIONS'))
    print(f'{methods:15} {rule.rule:60} → {rule.endpoint}')
" | sort -k2
```

That produces the ground truth. Adjust the plan if any of the URL/method assumptions above are wrong.
