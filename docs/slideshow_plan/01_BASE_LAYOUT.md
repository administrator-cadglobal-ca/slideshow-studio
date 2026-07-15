# 01 — Base Layout

The new `base.html` and the responsive navigation pattern every page inherits.

---

## Goals

1. **One base template**, one layout. All 22 templates extend it.
2. **Mobile: bottom nav.** Desktop: collapsible sidebar. Same nav items, rendered by different partials.
3. **HTMX** for partial updates (approving a user, submitting a form, loading more list items).
4. **Alpine.js** for local interactivity (opening bottom sheets, kebab menus, tab switches).
5. **Tailwind** compiled once at deploy time from `input.css` to `app.css`.
6. **No build system** for the app itself — Flask serves static files as-is.
7. **iOS safe-area insets** respected — content doesn't hide under the home indicator or notch.

---

## File map

```
app/
├── static/
│   ├── css/
│   │   └── app.css          ← Tailwind compiles to this. NOT hand-edited.
│   ├── js/
│   │   ├── app.js           ← Small file for app-specific JS (kept minimal)
│   │   ├── htmx.min.js      ← Self-hosted (14KB), from unpkg
│   │   └── alpine.min.js    ← Self-hosted (15KB), from unpkg
│   ├── fonts/
│   │   ├── InterTight-Variable.woff2
│   │   └── JetBrainsMono-Variable.woff2
│   └── favicon.ico
└── templates/
    └── shared/
        ├── base.html         ← Replaced by starter_templates/base.html
        ├── _bottom_nav.html  ← Mobile bottom nav partial
        ├── _desktop_sidebar.html  ← Desktop sidebar partial
        ├── _header.html      ← Top bar (page title + user menu)
        ├── _flash.html       ← Flash message rendering
        └── _footer.html      ← Optional footer
```

Templates in `starter_templates/` in this bundle are ready to copy into `app/templates/shared/`.

---

## Responsive layout structure

```
Mobile (default)                 Desktop (md: 768px+)
┌───────────────────────┐        ┌──────┬────────────────────────┐
│  Header (sticky)      │        │      │  Header                │
├───────────────────────┤        │      ├────────────────────────┤
│                       │        │      │                        │
│  Main content         │        │  S   │  Main content          │
│  (scrollable)         │        │  i   │  (scrollable)          │
│                       │        │  d   │                        │
│                       │        │  e   │                        │
│                       │        │  b   │                        │
│                       │        │  a   │                        │
│                       │        │  r   │                        │
│                       │        │      │                        │
├───────────────────────┤        │      │                        │
│  Bottom nav           │        │      │                        │
└───────────────────────┘        └──────┴────────────────────────┘
```

**Structural CSS:**
- Page root is a flex column, `min-height: 100dvh` (dynamic viewport unit — accounts for browser chrome).
- Main is `flex: 1` and scrolls internally on mobile so bottom nav stays fixed.
- Bottom nav has `padding-bottom: env(safe-area-inset-bottom)` for iPhone home indicator.
- Header has `padding-top: env(safe-area-inset-top)` for iPhone notch.
- Sidebar is hidden on mobile with `hidden md:flex`.
- Bottom nav is hidden on desktop with `md:hidden`.

---

## Navigation items

Same set of items in both nav renderings. The current active state is passed from the view context.

| Icon | Label | URL | Role required | Mobile nav | Desktop nav |
|---|---|---|---|---|---|
| `home` | Home | `/` | any user | ✓ (position 1) | ✓ |
| `folder` | Projects | `/projects` | any user | ✓ (position 2) | ✓ |
| `image` | Photos | `/photos` | any user | — | ✓ |
| `film` | Renders | `/renders` | any user | ✓ (position 3) | ✓ |
| `music` | Audio | `/audio` | any user | — | ✓ |
| `share-2` | Shared | `/shared` | any user | — | ✓ |
| `settings` | Settings | `/settings` | any user | ✓ (position 4) | ✓ (bottom) |
| `shield` | Admin | `/admin` | admin only | ✓ (position 5, admin only) | ✓ (bottom, admin only) |

**Mobile bottom nav shows max 5 items** — the "more" pattern (drawer with the rest) is disorienting on mobile. Everything essential is in the top 5.

**Desktop sidebar** groups Photos/Audio/Shared under a "Library" section header, keeps Home/Projects/Renders at the top for scan-first.

---

## Header (top bar)

Mobile and desktop, same shape but different content.

### Mobile
- Left: back arrow (when not root) OR menu icon (root)
- Center: page title (single line, truncated)
- Right: page-specific action icon (e.g., "+" on project list, kebab on detail views)

### Desktop
- Left: current section title + breadcrumb ("Users > Gurmeet Singh")
- Center: (empty)
- Right: search shortcut hint (Cmd+K) + user avatar dropdown (profile, sign out)

**Sticky?** Yes on mobile (with backdrop blur when scrolled). No on desktop (page scrolls under; sidebar is the anchor).

---

## Tailwind wiring

### Standalone Tailwind CLI (recommended)

We use the **standalone Tailwind CLI binary** — no Node.js, no npm, no `node_modules`. Download once, commit to repo (or fetch on deploy). See `starter_templates/build.sh`.

```bash
# One-time on Hetzner
curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64
chmod +x tailwindcss-linux-x64
sudo mv tailwindcss-linux-x64 /usr/local/bin/tailwindcss
```

### Build command

Runs at deploy time (or in a git hook, or manually when templates change):

```bash
cd /var/www/slideshow
tailwindcss \
  -i app/static/css/input.css \
  -o app/static/css/app.css \
  --config tailwind.config.js \
  --minify
```

The `--minify` flag produces production CSS. Typical output: 15-30KB gzipped, purged to only classes actually used in your templates.

**Deploy step to add:** append the above `tailwindcss` command to your existing `deploy/deploy.sh` after `pip install`, before `systemctl restart slideshow`.

### Watch mode (development on Windows or Linux)

```bash
tailwindcss -i input.css -o app.css --watch
```

Runs continuously, rebuilds on any template save. Adds ~200ms to save-refresh loop.

---

## HTMX wiring

HTMX enables server-driven partial updates. Instead of building an SPA with client-side state, the server returns HTML fragments; HTMX swaps them in.

### Loaded once in base.html

```html
<script src="{{ url_for('static', filename='js/htmx.min.js') }}" defer></script>
```

### CSRF integration

HTMX needs to send Flask-WTF's CSRF token on POST/PUT/DELETE requests. Add to base.html:

```html
<meta name="csrf-token" content="{{ csrf_token() }}">
<script>
  document.body.addEventListener('htmx:configRequest', (evt) => {
    evt.detail.headers['X-CSRFToken'] =
      document.querySelector('meta[name="csrf-token"]').content;
  });
</script>
```

### Common HTMX patterns used in the app

| Pattern | Attribute set | Example |
|---|---|---|
| Approve a pending user | `hx-post`, `hx-target`, `hx-swap` | Approve button posts, replaces the row with an updated one |
| Load more list items | `hx-get`, `hx-trigger="revealed"` | Infinite-scroll on user/project lists |
| Live search | `hx-get`, `hx-trigger="input changed delay:200ms"` | Search box updates the list as you type |
| Confirm-and-delete | `hx-confirm`, `hx-delete` | Native confirm dialog before firing |
| Optimistic UI | `hx-swap="outerHTML swap:200ms settle:200ms"` | Smooth transitions on row swap |

### Response fragment convention

Every HTMX endpoint returns a **template partial** (a `.html` file starting with `_`, e.g. `_user_card.html`) via `render_template('admin/_user_card.html', user=user)`. The Flask blueprint reuses the exact same partial that the full-page render uses. **One source of truth per component.**

---

## Alpine.js wiring

Alpine handles local interactivity that doesn't need the server: opening menus, toggling tabs, showing/hiding password fields, closing modals.

### Loaded once in base.html

```html
<script src="{{ url_for('static', filename='js/alpine.min.js') }}" defer></script>
```

### Common Alpine patterns

**Bottom sheet toggle:**
```html
<button @click="sheetOpen = true">Actions</button>

<div x-data="{ sheetOpen: false }">
  <div x-show="sheetOpen" @click.away="sheetOpen = false"
       class="bottom-sheet">
    <!-- sheet contents -->
  </div>
</div>
```

**Kebab menu:**
```html
<div x-data="{ open: false }" class="relative">
  <button @click="open = !open">⋮</button>
  <div x-show="open" x-transition @click.outside="open = false"
       class="absolute right-0 mt-2 …">
    <!-- menu items -->
  </div>
</div>
```

**Tabs:**
```html
<div x-data="{ tab: 'overview' }">
  <nav>
    <button @click="tab = 'overview'"
            :class="tab === 'overview' ? 'active' : ''">Overview</button>
    <button @click="tab = 'activity'"
            :class="tab === 'activity' ? 'active' : ''">Activity</button>
  </nav>
  <section x-show="tab === 'overview'"><!-- ... --></section>
  <section x-show="tab === 'activity'"><!-- ... --></section>
</div>
```

**Global stores** (rare — used for cross-page state like the user's theme preference):

```html
<script>
  document.addEventListener('alpine:init', () => {
    Alpine.store('theme', {
      current: localStorage.getItem('theme') || 'auto',
      set(v) { this.current = v; localStorage.setItem('theme', v); }
    });
  });
</script>
```

---

## Dark mode

Toggled by adding `class="dark"` on `<html>`. Tailwind's dark-mode variants (`dark:bg-gray-900`) handle the rest.

**Detection order:**
1. User's explicit preference (stored in localStorage)
2. System preference (`prefers-color-scheme`)
3. Default to light

**Toggle location:** Settings page, three-option radio (Auto / Light / Dark). Also a shortcut in the desktop user menu.

**Never** rely on system preference silently — some users on macOS have system-wide dark mode but want a specific app in light mode. Always let them override.

---

## Flash messages

Flask's flash messaging renders as toast notifications, not banners. The `_flash.html` partial:

```html
{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
    <div x-data="{ show: true }"
         x-show="show"
         x-init="setTimeout(() => show = false, 5000)"
         class="toast toast--{{ messages[0][0] }}">
      {{ messages[0][1] }}
      <button @click="show = false" aria-label="Dismiss">×</button>
    </div>
  {% endif %}
{% endwith %}
```

Categories: `success`, `error`, `warning`, `info`. Each has a color and icon.

**Undo toast pattern** (for suspend/delete actions):

```html
<div class="toast toast--info">
  User suspended.
  <button hx-post="/admin/users/{{ user.id }}/unsuspend"
          hx-swap="outerHTML"
          hx-target="closest .toast">Undo</button>
</div>
```

---

## Loading states

Every HTMX request should show that something's happening.

**Global request indicator:** a thin progress bar at the top of the page.

```html
<div id="htmx-indicator" class="htmx-indicator …"></div>
<style>
  .htmx-indicator { position: fixed; top: 0; left: 0; height: 2px;
                    background: var(--color-indigo); width: 0; }
  .htmx-request .htmx-indicator { width: 100%; transition: width 0.3s; }
</style>
```

**Skeleton placeholders:** for lists that take >200ms to load, render skeleton items server-side that HTMX then replaces with real content. See `_user_card_skeleton.html` in starter templates.

---

## Error boundaries

HTMX responses can fail. Handle globally:

```html
<script>
  document.body.addEventListener('htmx:responseError', (evt) => {
    const status = evt.detail.xhr.status;
    const message = status === 401 ? 'Session expired. Please sign in again.'
                  : status === 403 ? 'You don\'t have permission for that.'
                  : status === 404 ? 'Not found.'
                  : status >= 500 ? 'Server error. Try again in a moment.'
                  : 'Something went wrong.';
    showToast('error', message);
  });
</script>
```

Server always returns proper status codes. HTMX won't swap content on 4xx/5xx by default — good.

---

## What NOT to include in base.html

- jQuery — deleted, not needed with HTMX + Alpine
- Font Awesome / Icon fonts — replaced with inline Lucide SVGs per-use
- Bootstrap / any full CSS framework — Tailwind is the only CSS system
- Analytics scripts — decide later based on privacy stance; free option is Plausible self-hosted or Simple Analytics (paid). Not adding by default.
- Chat widgets, popup libraries, cookie banners — not needed for authenticated app
- Multiple font families beyond the three specified — leads to font-loading FOUT and CLS

Total base.html HTTP requests (uncached): 1 HTML + 1 CSS + 3 JS (htmx, alpine, app) + 2 fonts + 1 favicon = **8 requests, ~180KB total** on first load. Cache-friendly (all static files have version-hashed URLs via Flask's `url_for`).
