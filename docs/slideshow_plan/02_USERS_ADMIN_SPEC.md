# 02 — Users Admin Page (Pilot Rebuild)

Detailed spec for the mobile-first Users admin page. Once this pattern lands, extend to every other list/detail screen in the app.

---

## Scope

**In scope:**
- Users list (mobile card view / desktop table view)
- User detail view (opens as bottom sheet on mobile, side panel on desktop)
- All user actions: approve, edit, suspend, deactivate, reactivate, delete, adjust quota, reset OTP, impersonate
- Admin audit log (new — records every admin action)
- Filters: status, role
- Search: name, email, phone
- Bulk actions (desktop only, hidden behind "Select mode")

**Out of scope:**
- Signup/invitation flow (uses existing "signup request → admin approves" workflow)
- User's own profile page (that's `dashboard/profile.html`, a separate template)
- Role definitions themselves (using existing `role` column, values not changed)

---

## Data model refresher

Confirmed from existing schema:

```sql
CREATE TABLE users (
    id                    INTEGER PRIMARY KEY,
    email                 VARCHAR(255) NOT NULL UNIQUE,
    first_name            VARCHAR(100) NOT NULL,
    last_name             VARCHAR(100) NOT NULL,
    phone                 VARCHAR(30) NOT NULL UNIQUE,
    role                  VARCHAR(20),        -- 'super_admin' | 'admin' | 'member' | 'viewer'
    is_enabled            BOOLEAN,            -- approved by admin (post-signup)
    is_active             BOOLEAN,            -- can log in (False = suspended/deactivated)
    discount_code         VARCHAR(50),
    signup_message        TEXT,               -- user's note during signup
    approved_by           INTEGER REFERENCES users(id),
    approved_at           DATETIME,
    quota_bytes           BIGINT,
    notify_email          VARCHAR(255),       -- separate from login email
    google_access_token   TEXT,
    google_refresh_token  TEXT,
    google_token_expiry   DATETIME,
    google_email          VARCHAR(255),
    pref_transition       VARCHAR(20),
    pref_fps              INTEGER,
    pref_title_bg         VARCHAR(10),
    pref_title_color      VARCHAR(10),
    created_at            DATETIME,
    last_login            DATETIME
);
```

### Additive schema changes needed

New columns on `users`:
```sql
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

New table `admin_audit_log`:
```sql
CREATE TABLE admin_audit_log (
    id              INTEGER PRIMARY KEY,
    admin_user_id   INTEGER NOT NULL REFERENCES users(id),
    target_user_id  INTEGER REFERENCES users(id),
    target_type     VARCHAR(50) NOT NULL,   -- 'user', 'project', 'render', etc.
    action          VARCHAR(50) NOT NULL,   -- 'suspended', 'approved', 'quota_changed', ...
    payload_json    TEXT,                   -- action-specific details
    ip              VARCHAR(45),
    user_agent      VARCHAR(500),
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_audit_target ON admin_audit_log(target_type, target_user_id);
CREATE INDEX ix_audit_admin ON admin_audit_log(admin_user_id, created_at);
```

Both migrations are in `03_MIGRATION_PLAN.md` with rollback SQL.

---

## Status derivation

Every user has a computed status derived from flag combinations:

| `is_enabled` | `is_active` | `suspended_at` | Status |
|---|---|---|---|
| False | False | NULL | **Pending approval** (signup awaits admin) |
| True | True | NULL | **Active** |
| True | False | not NULL | **Suspended** (admin manually suspended; can be reactivated) |
| True | False | NULL | **Deactivated** (permanent, awaiting deletion) |
| False | True | any | *(shouldn't occur — treated as Pending)* |

Add a Python property on the User model:

```python
@property
def status(self):
    if not self.is_enabled:
        return 'pending'
    if self.suspended_at:
        return 'suspended'
    if not self.is_active:
        return 'deactivated'
    return 'active'
```

Also expose a display-friendly version and a color token per status for the Badge component.

---

## Routes

New routes in `blueprints/admin.py`. All require `@login_required` + `@admin_required` (add if missing).

### List and detail

| Method | URL | Handler | Returns |
|---|---|---|---|
| GET | `/admin/users` | `users_list()` | Full-page list |
| GET | `/admin/users?q=&status=&role=&sort=&page=` | `users_list()` | Full-page list with filters applied |
| GET | `/admin/users/partial` | `users_list_partial()` | Just the list container, for HTMX search/filter refresh |
| GET | `/admin/users/<int:id>` | `user_detail()` | Full-page detail (desktop) or side sheet content (mobile) |
| GET | `/admin/users/<int:id>/partial` | `user_detail_partial()` | Just the detail body, for HTMX-triggered refresh after actions |

### Actions (all POST, return updated partial via HTMX)

| Method | URL | Action | Returns |
|---|---|---|---|
| POST | `/admin/users/<int:id>/approve` | Set `is_enabled=True`, `approved_by=current_user`, `approved_at=now` | Updated user card / row |
| POST | `/admin/users/<int:id>/reject` | Delete (or archive) pending user | Empty div (row removed) |
| POST | `/admin/users/<int:id>/suspend` | Set `is_active=False`, `suspended_at=now`, `suspended_by=current_user`, `suspension_reason` from form | Updated card |
| POST | `/admin/users/<int:id>/reactivate` | Clear `suspended_at`, set `is_active=True` | Updated card |
| POST | `/admin/users/<int:id>/deactivate` | Set `is_active=False`, `deactivated_at=now`, `deactivated_by=current_user` | Updated card |
| POST | `/admin/users/<int:id>/delete` | Soft-delete (mark for cleanup) or hard-delete after grace period | Redirect to list |
| POST | `/admin/users/<int:id>/reset-otp` | Invalidate all active `auth_codes` for user | Toast confirmation |
| POST | `/admin/users/<int:id>/impersonate` | Store `original_user_id` in session, log in as target user | Redirect to `/` as target user |
| POST | `/admin/impersonate/stop` | Restore original session | Redirect to `/admin/users` |
| PATCH | `/admin/users/<int:id>/role` | Update role | Updated card |
| PATCH | `/admin/users/<int:id>/quota` | Update `quota_bytes` | Updated card |
| PATCH | `/admin/users/<int:id>/profile` | Update name/email/phone/notify_email | Updated card |
| GET | `/admin/users/<int:id>/audit` | List audit log entries for this user | Sub-tab in detail |

### Bulk (desktop-only, admin power feature)

| Method | URL | Action |
|---|---|---|
| POST | `/admin/users/bulk` | Body: `{ ids: [1,2,3], action: 'suspend', ... }` |
| GET | `/admin/users/export.csv` | CSV of all users |

---

## Mobile card layout (default, <768px)

```
┌──────────────────────────────────────────┐  ← page bg is --color-paper
│  ← Users                            + ✱ │  ← header, "+" opens invite sheet
├──────────────────────────────────────────┤
│                                          │
│  🔍  Search users…                   [×] │  ← sticky, always visible
│                                          │
│  ●─All  ○─Pending  ○─Suspended  ○─Admin │  ← horizontal-scroll filter chips
│                                          │
│  1 account · Sorted by recent login  ▾  │  ← count + sort control
│                                          │
│  ┌────────────────────────────────────┐ │
│  │  ┌──┐                              │ │
│  │  │GS│  Gurmeet Singh          ⋯   │ │ ← Card, whole card is tappable
│  │  └──┘  gurmeet.singh@cadglobal.ca │ │
│  │        +1 (403) ••• •••1          │ │
│  │        ● Active · Admin           │ │ ← badge row
│  │        ▓▓░░░░░░░░  2.4 / 100 GB  │ │ ← storage meter
│  │        Last seen 2 min ago        │ │
│  └────────────────────────────────────┘ │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │  ┌──┐                              │ │
│  │  │AK│  Anita Kumar            ⋯   │ │
│  │  └──┘  anita@example.com          │ │
│  │        +1 (403) ••• •••4          │ │
│  │        ○ Pending approval         │ │
│  │        Signed up 3h ago           │ │
│  │        [Approve]      [Reject]    │ │ ← inline actions for pending
│  └────────────────────────────────────┘ │
│                                          │
│                                          │  ← infinite scroll: more load on scroll
├──────────────────────────────────────────┤
│    🏠     📁     🎞      ⚙     🛡      │  ← bottom nav, Admin highlighted
└──────────────────────────────────────────┘
```

### Card anatomy

- **Avatar** — 44×44px circle with initials on a color derived from user id (consistent per-user)
- **Primary line** — full name (bold, `text-h3`)
- **Kebab** (⋯) — 44×44px hit area; opens bottom sheet with all actions
- **Email** — mono variant, `text-small`, `--color-ink-soft`
- **Phone** — mono variant, `text-small`, masked
- **Badges** — status dot + label + role, single line
- **Storage meter** — 4px height bar, indigo fill, `--color-line-soft` track
- **Timestamp** — relative ("2 min ago") with tooltip showing absolute
- **Inline actions** — only shown for status='pending', two ghost buttons

### Card tap → opens detail as bottom sheet

- Sheet slides up from bottom, 90% viewport height, backdrop overlay
- Draggable handle at top; drag down to dismiss
- Scrollable content inside sheet
- Bottom action bar sticky within sheet if actions are present

### Kebab tap → opens action bottom sheet

Small bottom sheet (auto-height), lists actions relevant to user's status. Example for Active user:

```
┌──────────────────────────────────────┐
│              ─                       │  ← drag handle
│                                      │
│  Actions for Anita Kumar             │
│                                      │
│  📝  Edit user…                      │
│  🔑  Reset OTP                       │
│  👤  Impersonate                     │
│  ⏸   Suspend…                        │
│  🚫  Deactivate…                     │
│  🗑   Delete…                         │
│                                      │
│  [Cancel]                            │
└──────────────────────────────────────┘
```

Actions with "…" open a confirmation sub-sheet with reason input where relevant.

---

## Desktop table layout (≥1024px)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Users > Overview                                    Cmd+K   [avatar] ▾   │
├──────┬─────────────────────────────────────────────────────────────────────┤
│      │                                                                     │
│  🏠  │  Users                            [Select] [Export]  [+ Invite]   │
│  📁  │                                                                     │
│  🎞  │  🔍 Search users…              [Status ▾] [Role ▾]  Sort: Recent ▾ │
│  📷  │                                                                     │
│  🎵  │  ┌───────────────────────────────────────────────────────────────┐ │
│  🔗  │  │ □  User            Contact         Status    Storage      Actions │
│      │  ├───────────────────────────────────────────────────────────────┤ │
│  ─── │  │ □  GS Gurmeet S.   +1(403)…1      ● Active  ▓▓ 2.4/100    ⋯   │ │
│  ⚙   │  │    gurmeet.si…                                                │ │
│  🛡  │  │                                                                │ │
│      │  │ □  AK Anita K.     +1(403)…4      ○ Pending -              ⋯  │ │
│      │  │    anita@ex…                                                   │ │
│      │  └───────────────────────────────────────────────────────────────┘ │
│      │                                                                     │
│      │  1 account · Page 1 of 1                                           │
└──────┴─────────────────────────────────────────────────────────────────────┘
```

### Table anatomy

- **Sticky header** with sortable columns (click header to sort, indicator chevron)
- **Row height** 72px (accommodates two-line user cell)
- **Hover state**: row background shifts to `--color-line-soft`
- **Kebab per row** on hover; always visible on touch devices
- **Row click** opens side panel (fixed-position, 480px wide, slides in from right)
- **Select checkboxes** hidden by default; "Select" button in header enables select mode

### Side panel (desktop detail)

- Slides in from right, 480px wide, overlays content beneath
- Not a modal — main content is visible and semi-scrollable behind
- ESC or click-outside to dismiss
- Same content as mobile bottom sheet, longer form-factor

---

## Detail view content (same on both platforms)

Sections stacked vertically. Sticky header with user summary.

### 1. Identity block (always visible)

```
        [avatar]
        Gurmeet Singh                 ← Editable inline (pencil icon on hover)
        gurmeet.singh@cadglobal.ca
        +1 (403) 555-0123
        ● Active · Admin              ← badges
        Signed up Jul 14, 2026
```

### 2. Actions row

Primary actions inline as ghost buttons:
```
[Impersonate]  [Reset OTP]  [Send message]
```

Kebab (⋮) for the rest:
```
Edit profile…
Adjust quota…
Change role…
─────────────
Suspend…
Deactivate…
Delete…
```

### 3. Storage

```
Storage
▓▓▓▓░░░░░░░░░░░░░░  2.4 GB of 100 GB (2.4%)
Photos: 1.8 GB · Videos: 0.6 GB · Audio: 12 MB · Thumbs: 40 MB
```

For active projects only. Deleted content shown separately if quota policy counts it.

### 4. Recent activity

```
Last login    2 min ago from Calgary, AB (Chrome / Windows)
Sessions      1 active — [Revoke all]
Total logins  4 all-time
```

### 5. Projects (collapsible)

```
Projects (3)
› Diwali Mela 2026 · 47 photos · Rendered
› Simran & Arjun Wedding · 312 photos · Draft
› Vaisakhi Nagar Kirtan · 89 photos · Rendered
                                  [See all]
```

### 6. Audit log (collapsible, most recent 5)

```
Recent admin activity
Jul 14, 10:52  Approved by Gurmeet Singh
Jul 14, 09:15  Signed up
                                  [See full log]
```

### 7. Danger zone (collapsible, collapsed by default)

Three destructive actions with confirmation flow:
- **Suspend** — user can't log in; data preserved; reversible
- **Deactivate** — user can't log in; data marked for cleanup in 30 days
- **Delete** — hard-delete user + data; requires typing email to confirm

---

## State + interaction flows

### Pending user → approve

1. Admin sees pending user card with inline "Approve" and "Reject" buttons
2. Admin taps Approve
3. HTMX POST to `/admin/users/<id>/approve`
4. Server sets `is_enabled=True, approved_by=current_user, approved_at=now`, writes audit log entry, dispatches welcome email
5. Server returns updated card partial with Active status
6. HTMX swaps card in place; small transition (fade out old, fade in new)
7. Toast: "Anita Kumar approved."

### Active user → suspend

1. Admin taps kebab, selects "Suspend…" from bottom sheet
2. Confirmation sub-sheet opens with textarea for reason
3. Admin enters reason (required), taps "Suspend"
4. HTMX POST to `/admin/users/<id>/suspend` with `reason` in form data
5. Server sets `is_active=False, suspended_at=now, suspended_by=current_user, suspension_reason=…`, writes audit log entry, invalidates active sessions
6. Server returns updated card partial with Suspended status
7. Toast with undo: "Anita Kumar suspended. [Undo]"
8. If undo clicked within 5s, POST to reactivate

### Any admin action → audit log

Every state-changing admin action writes a row to `admin_audit_log`:

```python
def log_admin_action(action, target_user_id=None, payload=None):
    entry = AdminAuditLog(
        admin_user_id=current_user.id,
        target_user_id=target_user_id,
        target_type='user',
        action=action,
        payload_json=json.dumps(payload) if payload else None,
        ip=request.remote_addr,
        user_agent=request.user_agent.string[:500],
    )
    db.session.add(entry)
    # Commit happens with the surrounding transaction
```

Actions to log: `approved`, `rejected`, `suspended`, `reactivated`, `deactivated`, `deleted`, `role_changed`, `quota_changed`, `profile_edited`, `otp_reset`, `impersonate_start`, `impersonate_stop`.

### Impersonate flow

1. Admin taps "Impersonate" on user detail
2. Confirmation dialog: "Log in as Anita Kumar? A banner will show that you're impersonating until you stop."
3. On confirm: server stores `original_user_id` in session, calls `login_user(target)`, writes audit log
4. Server redirects to `/`
5. Every page now shows a persistent banner: "Impersonating Anita Kumar — [Stop impersonating]"
6. Actions taken during impersonation are audit-logged with a special flag
7. "Stop impersonating" restores original session

---

## Empty states

**No pending users:**
```
       ✓
No one waiting
When someone signs up, they'll show up here for you to approve.
```

**No suspended users:**
```
       ○
No suspended users
Users you suspend will appear here.
```

**Search returns nothing:**
```
       🔍
No matches for "xyz"
Try a different search term or clear filters.
[Clear search]
```

---

## Permissions

- **`super_admin`** — all actions, including deleting other admins
- **`admin`** — all actions except modifying `super_admin` accounts
- **`member`** / **`viewer`** — no access to `/admin/*` at all (redirect to `/`)

Enforced at blueprint level via `@admin_required` decorator that checks `current_user.role in ('admin', 'super_admin')`. Additional per-action checks in view functions.

**Impersonation restriction:** admins cannot impersonate other admins or super_admins. Only members/viewers. Removes the risk of an admin using impersonation to escalate privileges silently.

---

## Success criteria (how you know this is done)

- [ ] `/admin/users` renders correctly at 375px (iPhone SE) and 1920px (desktop)
- [ ] All 10 actions (approve, suspend, reactivate, deactivate, delete, role change, quota change, profile edit, OTP reset, impersonate) work end-to-end
- [ ] Every action writes an audit log entry
- [ ] Bottom nav visible on mobile, sidebar on desktop
- [ ] Bottom sheet on mobile, side panel on desktop, for user detail
- [ ] Search returns results in <200ms (uses SQLite LIKE on indexed columns)
- [ ] Filter chips work: All, Pending, Suspended, Deactivated, by Role
- [ ] Undo toast works for suspend, deactivate
- [ ] Impersonate banner shows and stop-impersonating restores session
- [ ] Dark mode toggles correctly, no ink-on-ink or paper-on-paper mistakes
- [ ] Keyboard nav: Tab through all interactive elements in logical order
- [ ] Screen reader announces status changes correctly
