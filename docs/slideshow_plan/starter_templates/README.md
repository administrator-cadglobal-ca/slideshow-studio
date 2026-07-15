# Starter Templates — Installation

Ready-to-use files that seed the mobile-first rebuild. Copy them into the app's tree, install Tailwind, run the build, restart the service.

---

## What's in this folder

| File | Destination in app tree |
|---|---|
| `base.html` | `app/templates/shared/base.html` (replaces existing) |
| `_user_card.html` | `app/templates/admin/_user_card.html` (new) |
| `_bottom_nav.html` | `app/templates/shared/_bottom_nav.html` (new) |
| `_desktop_sidebar.html` | `app/templates/shared/_desktop_sidebar.html` (new) |
| `tailwind.config.js` | `tailwind.config.js` (repo root, new) |
| `input.css` | `app/static/css/input.css` (new; not the compiled output) |
| `build.sh` | `build.sh` (repo root or wherever your deploy scripts live) |

---

## Prerequisite one-time setup on Hetzner

### 1. Install Tailwind standalone CLI

No Node.js required. One binary, ~25MB.

```bash
curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64
chmod +x tailwindcss-linux-x64
sudo mv tailwindcss-linux-x64 /usr/local/bin/tailwindcss
tailwindcss --help | head -1
# Should print: tailwindcss v4.x.x
```

Or run `build.sh` once — it auto-installs the CLI on first run.

### 2. Self-host the JS libraries

Download once, commit to repo (or fetch during deploy):

```bash
cd /var/www/slideshow/app/static/js/

# HTMX (14 KB minified)
curl -sLO https://unpkg.com/htmx.org@2.0.6/dist/htmx.min.js

# Alpine.js (15 KB minified)
curl -sL -o alpine.min.js https://unpkg.com/alpinejs@3.14.9/dist/cdn.min.js

ls -la htmx.min.js alpine.min.js
```

### 3. Self-host the fonts

Two font files, both variable (single file per family, all weights):

```bash
mkdir -p /var/www/slideshow/app/static/fonts
cd /var/www/slideshow/app/static/fonts

# Inter Tight — Google Fonts
# Download from https://fonts.google.com/specimen/Inter+Tight and rename
# Or use a CDN mirror:
curl -sL -o InterTight-Variable.woff2 \
  "https://fonts.gstatic.com/s/intertight/v6/NaN4epOXO_LZbEE-VXOB86Jr1zBHnGqIepZQKPk.woff2"

# JetBrains Mono — Google Fonts
curl -sL -o JetBrainsMono-Variable.woff2 \
  "https://fonts.gstatic.com/s/jetbrainsmono/v20/tDbY2o-flEEny0FZhsfKu5WU4zr3E_BX0PnT8RD8yKxjPVmUsaaDhw.woff2"

ls -la
```

The URLs above are stable Google Fonts static endpoints. If they change over time, download the woff2 variable files from https://fonts.google.com manually.

---

## Installation steps

Run these on Hetzner, from `/var/www/slideshow`.

```bash
cd /var/www/slideshow

# 1. Back up existing base template (safety net)
cp app/templates/shared/base.html app/templates/shared/base.html.bak.$(date +%Y%m%d)

# 2. Copy starter template files into place (assuming they've been uploaded to /tmp/starter_templates/)
cp /tmp/starter_templates/base.html              app/templates/shared/base.html
cp /tmp/starter_templates/_bottom_nav.html       app/templates/shared/_bottom_nav.html
cp /tmp/starter_templates/_desktop_sidebar.html  app/templates/shared/_desktop_sidebar.html
cp /tmp/starter_templates/_user_card.html        app/templates/admin/_user_card.html
cp /tmp/starter_templates/tailwind.config.js     tailwind.config.js
cp /tmp/starter_templates/input.css              app/static/css/input.css
cp /tmp/starter_templates/build.sh               build.sh
chmod +x build.sh

# 3. Create a stub _header.html and _flash.html (base.html references them)
cat > app/templates/shared/_header.html <<'EOF'
<header class="h-16 flex items-center px-4 md:px-8 border-b border-line sticky top-0 z-20 bg-paper/90 backdrop-blur">
  <h1 class="text-h2 truncate">{% block page_title %}{% endblock %}</h1>
</header>
EOF

cat > app/templates/shared/_flash.html <<'EOF'
{% with messages = get_flashed_messages(with_categories=true) %}
  {% for category, message in messages %}
    <div x-data="{ show: true }" x-show="show" x-init="setTimeout(() => show = false, 5000)"
         class="toast-{{ 'success' if category == 'success' else 'error' if category == 'error' else 'info' }}">
      <span>{{ message }}</span>
      <button @click="show = false" class="ml-auto opacity-70 hover:opacity-100" aria-label="Dismiss">×</button>
    </div>
  {% endfor %}
{% endwith %}
EOF

# 4. Build the CSS for the first time
./build.sh

# 5. Restart the app
systemctl restart slideshow
sleep 3
systemctl status slideshow --no-pager | head -5

# 6. Verify
curl -I https://app.calgarydhamaka.com
curl -sI https://app.calgarydhamaka.com/static/css/app.css | head -3
```

Open https://app.calgarydhamaka.com in a browser. The pages will look different — new fonts, warmer background — but all existing functionality should work.

---

## Adding the build step to deploys

Append to `deploy/deploy.sh`, before the `systemctl restart` line:

```bash
# Build Tailwind CSS
cd "$APP_ROOT"
./build.sh
```

That's it. Every future deploy rebuilds `app.css` from current templates.

---

## Watch mode for development

If you're editing templates on Hetzner directly (unusual — most people would develop on Windows/Mac and deploy):

```bash
./build.sh --watch
```

Runs continuously, rebuilds within ~200ms of any template save.

If you're on Windows editing templates in VS Code that live on your local disk and syncing to Hetzner: install the Tailwind CLI locally (`npm i -g tailwindcss` OR grab the Windows binary from the same GitHub releases), and add a watch task to your editor. Only the compiled `app.css` needs to reach the server.

---

## Rollback

If anything looks broken after installation:

```bash
cd /var/www/slideshow
cp app/templates/shared/base.html.bak.YYYYMMDD app/templates/shared/base.html
systemctl restart slideshow
```

The old CSS still lives in `app/static/css/app.css` (before we overwrote it with the Tailwind build). Keep a backup of the old app.css too:

```bash
cp app/static/css/app.css app/static/css/app.css.pre-tailwind
# Then run ./build.sh
# If rollback needed: cp app.css.pre-tailwind app.css
```

---

## Verification checklist

After installation, check:

- [ ] `curl -I https://app.calgarydhamaka.com` returns 200
- [ ] `curl -I https://app.calgarydhamaka.com/static/css/app.css` returns 200
- [ ] `curl -I https://app.calgarydhamaka.com/static/js/htmx.min.js` returns 200
- [ ] `curl -I https://app.calgarydhamaka.com/static/js/alpine.min.js` returns 200
- [ ] `curl -I https://app.calgarydhamaka.com/static/fonts/InterTight-Variable.woff2` returns 200
- [ ] Login page loads in browser without console errors
- [ ] Dashboard renders after login
- [ ] Mobile bottom nav appears at 375px viewport (Chrome DevTools device toolbar)
- [ ] Desktop sidebar appears at 1024px viewport
- [ ] Dark mode toggle works (if wired in profile page)
- [ ] Font "Inter Tight" is loading (inspect element → Computed → font-family should show Inter Tight)

---

## Troubleshooting

**`app.css` is empty or 1 KB:** Tailwind didn't find any templates. Check that `tailwind.config.js` `content:` paths point at `app/templates/**/*.html`.

**Fonts don't load:** check the actual paths in `input.css` (`/static/fonts/...`) match your Flask app's static URL prefix. If your app uses `/static/` prefix (default), no change needed.

**HTMX CSRF errors on POST:** verify `<meta name="csrf-token">` renders in `base.html` (requires Flask-WTF to be initialized in the app).

**Bottom nav overlaps content:** verify `<main>` has `pb-20 md:pb-6` (padding-bottom on mobile only) — this is in the provided base.html.

**Sidebar and content overlap:** verify the main content column has `md:pl-60` (matches sidebar width of 240px).

**"Inter Tight" font-weight looks wrong:** confirm you downloaded the **variable** woff2, not a single-weight file. Variable files support weights 100-900 in one file.
