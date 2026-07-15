# Slideshow Studio — Mobile-First Rebuild Plan

**Prepared:** 14-Jul-2026
**For:** Gurmeet Singh, CAD Global Inc.
**Target app:** Slideshow Studio (Calgary Dhamaka) at `https://app.calgarydhamaka.com`

---

## What this bundle is

A complete planning package for rebuilding Slideshow Studio's 22-template Flask app as mobile-first, using a zero-cost stack (Jinja + HTMX + Alpine.js + Tailwind CSS). The pilot rebuild target is the Users admin page, with the same patterns then extended across the whole app.

Nothing in this bundle changes your running production app. These are specs, plans, and reference templates. You (or a future Claude session) execute against them.

---

## Reading order

Read in this order the first time through. Later, jump to whichever doc is relevant.

1. **`00_DESIGN_SYSTEM.md`** — the visual foundation: palette, typography, spacing, breakpoints, component inventory. The vocabulary the rest of the plan uses.
2. **`01_BASE_LAYOUT.md`** — the new `base.html` structure: how HTMX/Alpine/Tailwind are wired, the responsive navigation pattern (bottom nav on mobile, sidebar on desktop), and dark mode support.
3. **`02_USERS_ADMIN_SPEC.md`** — the pilot rebuild in full detail: routes, wireframes, actions, states, permissions. This is the template pattern all other rebuilds follow.
4. **`03_MIGRATION_PLAN.md`** — how to migrate 22 templates without breaking the live app: priority order, "strangler fig" approach, feature flags, rollback plan.
5. **`04_TASK_BREAKDOWN.md`** — sequenced work packets, each independently mergeable. Estimated effort per packet.
6. **`05_ROUTES_INVENTORY.md`** — map of what each blueprint does today and what URLs are exposed.

---

## `starter_templates/`

Ready-to-use files that seed the rebuild:

- **`base.html`** — drop-in replacement for `app/templates/shared/base.html`
- **`_user_card.html`** — component partial demonstrating the card pattern used across the app
- **`_bottom_nav.html`** — mobile bottom navigation partial
- **`_desktop_sidebar.html`** — desktop sidebar partial
- **`tailwind.config.js`** — Tailwind config with design tokens baked in
- **`input.css`** — Tailwind entry point + custom component classes
- **`build.sh`** — one-command Tailwind CSS build (uses standalone binary, no Node.js needed)
- **`starter_templates/README.md`** — installation instructions

---

## Non-negotiables carried into the plan

Extracted from the conversation that produced this bundle:

- **Zero recurring cost** — no paid SaaS in the critical path. Only ongoing costs remain Hetzner (~€8/mo) and the domain.
- **Mobile-first for the whole app** — not just admin. Every screen designed for 380px viewport first, then progressively enhanced upward.
- **Passwordless email-OTP login** — email required at signup, phone required but not used for login. OTP delivered via existing Hostinger SMTP configuration.
- **Keep the current stack** — Flask + Jinja + SQLAlchemy stay. No SPA rewrite. Add HTMX + Alpine + Tailwind alongside.
- **Signup requires admin approval** — the existing `approved_by` / `approved_at` flow is preserved and made first-class in the UI.
- **Community subject matter** — the design is grounded in North Indian community events (Punjabi and Rajasthani wedding celebrations, Diwali, Lohri, Vaisakhi, cultural nights, community awards), not sterile B2B SaaS aesthetics. Calgary Dhamaka's audience skews heavily Punjabi/Sikh with strong North Indian Hindu representation — the visual language reflects that specifically, rather than a generic pan-Asian gesture.

---

## What's NOT in this bundle

- **Backend refactor** — the Users table schema is already rich enough. This plan doesn't change the SQLAlchemy models.
- **Auth flow overhaul** — that's a parallel task in your backlog. This plan assumes email-OTP login works by the time the rebuild lands.
- **Render pipeline** — separate concern. Celery / Redis / `slideshow_maker.py` upload are unchanged by this rebuild.
- **Deployment automation** — Tailwind build step needs to be added to your deploy pipeline, but that's a one-line change explained in `starter_templates/README.md`.
