# 04 — Task Breakdown

Each task is a discrete, mergeable, testable unit. Ordered by dependency. Effort estimates in "focused hours" (assuming Claude-assisted implementation).

---

## Phase A — Foundation (Wave 1)

### A1. Design system infrastructure (2h)

**Deliverables:**
- Download Tailwind standalone CLI to Hetzner and `/usr/local/bin`
- Add `starter_templates/tailwind.config.js` → repo root as `tailwind.config.js`
- Add `starter_templates/input.css` → `app/static/css/input.css`
- Run Tailwind build once to produce `app/static/css/app.css`
- Add build step to `deploy/deploy.sh`
- Download Inter Tight + JetBrains Mono woff2 files to `app/static/fonts/`
- Self-host htmx.min.js and alpine.min.js in `app/static/js/`

**Verification:** `curl -I https://app.calgarydhamaka.com/static/css/app.css` returns 200 with Tailwind-compiled CSS.

**No user-visible change yet** — templates still use the old base.

### A2. New base.html + partials (2h)

**Deliverables:**
- Replace `app/templates/shared/base.html` with the new one
- Add `_bottom_nav.html`, `_desktop_sidebar.html`, `_header.html`, `_flash.html` partials
- Wire HTMX + Alpine loading in base
- Wire CSRF token integration for HTMX
- Add global error handler for HTMX responses
- Add dark mode detection + toggle logic

**Verification:** Every existing page loads. All still functional. Different fonts and slightly different chrome are visible.

**Rollback:** Git revert base.html changes. Old CSS still works because Tailwind classes don't conflict with existing selectors.

### A3. Design system component library documentation (2h)

**Deliverables:**
- Create `app/templates/_components/` folder with reference examples of every component (buttons, cards, forms, modals, sheets, badges)
- Not routed — just files with commented HTML that future templates copy from
- One example per component; if a component has variants, show all

**Verification:** N/A — this is a reference for future work. Consider it "docs as code."

---

## Phase B — Auth (Wave 2)

### B1. Login page rebuild (1.5h)

**Deliverable:** `auth/login.html` rewritten. Single email input, "Send code" button, dark mode, mobile-first.

**Uses:** Card component, input component, button component.

**Special:** existing route in `blueprints/auth.py` doesn't change — only the template.

### B2. OTP verify page rebuild (2h)

**Deliverable:** `auth/verify.html` rewritten with segmented OTP input (8 chars, auto-advance, paste handling).

**Component:** New `OtpInput` component. Alpine.js for the character-by-character focus management.

**Special features:**
- `inputmode="text"` `autocapitalize="characters"` so mobile keyboard shows caps
- Paste-from-clipboard fills all 8 chars, auto-submits
- Resend button with 30-second cooldown countdown
- Different email link goes back to login

### B3. Signup pages rebuild (2h)

**Deliverables:** `auth/register.html` (email + phone + first name + last name + optional message) and `auth/register_done.html` (waiting-for-approval state).

**Special:**
- Phone input uses `type="tel"` + auto-formatting to `+1 (XXX) XXX-XXXX`
- Real-time email validation (client-side format check only)
- "Signup message" field explains its purpose ("What will you use this for?")

---

## Phase C — Dashboard & Profile (Wave 3)

### C1. Dashboard hub page (3h)

**Deliverable:** `dashboard/index.html` rewritten.

**Layout mobile:**
- Big "Create slideshow" CTA at top if user has 0 projects
- Recent projects grid (2 cols on mobile, 3 on desktop)
- Storage usage card
- Recent renders row

**Layout desktop:**
- Sidebar showing nav (from Wave 1)
- Multi-column grid, wider layout

**Empty state:** hero illustration + "Create your first slideshow" CTA + link to short walkthrough.

### C2. Profile page rebuild (2h)

**Deliverable:** `dashboard/profile.html` rewritten.

**Sections:**
1. Identity (name, email, phone, notify_email)
2. Slideshow preferences (default transition, FPS, title colors)
3. Security (change email/phone, active sessions, sign out all)
4. Storage (usage bar + link to buy more if you add plans later)
5. Danger zone (delete account)

---

## Phase D — Projects (Wave 4)

### D1. Projects list (2h)

**Deliverable:** `projects/index.html` — grid of project cards.

**Card content:** thumbnail (from first photo), title, photo count, status (draft/rendered), last modified.

**Actions per card:** open, rename, duplicate, delete (via kebab).

**Filters:** All / Drafts / Rendered.

### D2. New project flow (1.5h)

**Deliverable:** `projects/new.html` — create form.

**Fields:** title, optional description, template picker (grid of visual templates).

**Post-create:** redirect to `projects/show.html` for the new project.

### D3. Project settings (1.5h)

**Deliverable:** `projects/settings.html` — per-project config.

**Sections:** basics (title, description), timing (per-photo duration, transitions), music (link to audio library), title cards (colors, fonts), advanced (custom FFmpeg args if power user).

### D4. Project notes (0.5h)

**Deliverable:** `projects/notes.html` — Markdown-rendered notes attached to a project.

Simple textarea + preview toggle. HTMX autosave on blur.

### D5. Project workspace (5h — largest single template)

**Deliverable:** `projects/show.html` — the main editing surface.

**Mobile layout:**
- Header: project title + kebab
- Photo grid (2 cols, 3 on landscape phones)
- Long-press to select multiple
- Bottom action bar appears in selection mode
- Bottom sheet: upload photos, reorder, add music, render

**Desktop layout:**
- Photo grid (5-6 cols)
- Sidebar: project info, quick actions
- Top: bulk actions when selected

**Photo interactions:**
- Tap to view fullscreen (basic gallery)
- Long-press / right-click for kebab menu
- Drag to reorder (HTMX POST on drop with new position)

**Upload:**
- Multi-file input with drag-drop zone
- Progress bars per file
- HTMX-driven upload progress

### D6. Project preview (3h)

**Deliverable:** `projects/preview.html` — plays the slideshow in-browser before render.

**Uses:** HTML5 `<img>` + CSS transitions to preview the actual slideshow behavior without ffmpeg. Not exact but close enough for confidence check.

**Controls:** play/pause, previous/next photo, transition speed slider, fullscreen.

---

## Phase E — Renders (Wave 5)

### E1. Renders list (1.5h)

**Deliverable:** `renders/index.html` — history of renders.

**Row content:** project name, resolution, duration, status, file size, timestamp, download button (if completed).

**Empty state:** "No renders yet. Open a project and hit Render."

### E2. Render detail + progress (2.5h)

**Deliverable:** `renders/show.html` — active render page.

**States:**
- **Queued** — waiting for Celery worker
- **Rendering** — progress bar, ETA, current photo being processed, live log (HTMX polling)
- **Completed** — download button + share link + "Play in browser" preview
- **Failed** — error message + retry button + copy-error-for-support

**Real-time updates:** HTMX polls `/renders/<id>/status.partial` every 3 seconds while rendering. Stops polling on terminal states.

---

## Phase F — Audio Library (Wave 6)

### F1. Audio index (1.5h)

**Deliverable:** `audio/index.html` — uploaded audio files.

Grid or list view (user toggle). Metadata: title, duration, file size, waveform thumbnail (pre-generated on upload).

### F2. Audio clips list (1h)

**Deliverable:** `audio/clips.html` — clips derived from source audio files.

### F3. Audio labels (1h)

**Deliverable:** `audio/labels.html` — tag management for organizing audio.

### F4. Waveform clip editor (5h — hardest non-admin)

**Deliverable:** `audio/clip_editor.html`.

**Features:**
- Waveform rendered via canvas (uses server-generated peaks data)
- Draggable start/end handles
- Play button plays only the selected range
- Fine-tune with keyboard arrows
- Preview loop toggle
- Save creates a new clip

**Mobile:** pinch to zoom on waveform, drag handles with generous touch targets.

---

## Phase G — Admin (Wave 7 — the pilot)

### G1. Schema migrations (0.5h)

Apply migrations 001 (user status columns) and 002 (admin_audit_log). See `03_MIGRATION_PLAN.md`.

### G2. Admin dashboard (2h)

**Deliverable:** `admin/index.html` — admin home.

**Sections:**
- Stats row: total users, pending approvals, active in last 24h, storage used total
- Pending approvals (if any) — top 5, "See all" link
- Recent admin actions (last 10 from audit log)
- Health status: services (Redis, Celery worker, ffmpeg version, disk space)

### G3. Users list (4h — the pilot)

**Deliverable:** `admin/users.html` — full spec in `02_USERS_ADMIN_SPEC.md`.

Break into subtasks:
- G3a. Card component (`_user_card.html`)
- G3b. Search + filters
- G3c. Sort + pagination
- G3d. Row-level actions (kebab bottom sheet)
- G3e. Detail sheet (mobile) / side panel (desktop)
- G3f. All 10 action endpoints and their audit log calls

### G4. Requests page merged into users (1h)

**Deliverable:** Either delete `admin/requests.html` entirely (in favor of the "Pending" filter chip on users list) or reduce it to a simple redirect. Recommendation: delete.

### G5. Impersonation infrastructure (2h)

**Deliverable:**
- Session helper to swap current user
- Persistent banner showing when impersonating
- Restrictions: can only impersonate members/viewers
- Audit log entries for start/stop
- All actions during impersonation flagged in audit

---

## Phase H — Share (Wave 8)

### H1. Public share player (3h)

**Deliverable:** `share/player.html` — public-facing slideshow player.

**Special design considerations:**
- No app chrome (no nav, no header) — the photos are the star
- Auto-play on load with option to pause
- Full-screen by default on mobile
- Share buttons at bottom: copy link, WhatsApp, Facebook, download MP4
- Attribution: "Made with Slideshow Studio" tiny footer link

---

## Phase I — Polish (post-migration)

### I1. Accessibility audit (2h)

- Run axe DevTools on every page
- Fix any WCAG AA violations
- Manual keyboard nav test
- VoiceOver / NVDA test on 3 key flows

### I2. Performance audit (2h)

- Lighthouse mobile scores per page
- Target: Performance 90+, Accessibility 100
- Optimize any pages below threshold
- Add loading skeletons where perceived latency > 500ms

### I3. Documentation for future contributors (1h)

- Update repo README with new stack info
- Component library overview page
- How to add a new template using the design system

---

## Total effort summary

| Phase | Deliverables | Est. hours |
|---|---|---|
| A — Foundation | 3 tasks | 6h |
| B — Auth | 3 tasks | 5.5h |
| C — Dashboard | 2 tasks | 5h |
| D — Projects | 6 tasks | 13.5h |
| E — Renders | 2 tasks | 4h |
| F — Audio | 4 tasks | 8.5h |
| G — Admin (pilot) | 5 tasks | 9.5h |
| H — Share | 1 task | 3h |
| I — Polish | 3 tasks | 5h |
| **Total** | **29 tasks** | **~60h** |

Realistically 20-25 focused sessions with Claude assistance. At 2 sessions per week, that's a **12-week rebuild**. Can be compressed if you push through several waves in a single day.

---

## Recommended immediate first steps (next session)

1. **Task A1** — get Tailwind building on Hetzner, fonts self-hosted, HTMX + Alpine downloaded. 2 hours. Nothing user-visible changes.
2. **Task A2** — swap in the new base.html + partials. 2 hours. Every page now uses the new chrome. Small visual regression review.
3. **Verify** for 24-48 hours that no existing page broke.
4. **Task B1** — rebuild login page. Small, contained, immediate visual win.

That's a productive first session that ships value without opening the whole app for a rewrite mid-flight.
