# 00 — Design System

The visual and interaction foundation. Every subsequent screen references tokens defined here.

---

## Design thesis

Slideshow Studio is a tool for **community memory-keepers in Calgary's North Indian diaspora**: the volunteer photographer at a Diwali mela or Lohri bonfire, the aunt with 400 wedding photos on her phone from a three-day Punjabi shaadi, the community-events lead assembling a highlight reel for a Vaisakhi celebration or the gurdwara AGM. Calgary Dhamaka's user base skews heavily Punjabi/Sikh with strong North Indian Hindu representation, and the design speaks to that specifically rather than reaching for a generic pan-Asian gesture.

The design should feel like a warm workshop — capable, unfussy, celebratory in reserve rather than in ornament.

**We reject three defaults for this brief:**

1. The "warm cream + terracotta serif" AI-design cliché — too generic to signal anything about this community.
2. Corporate dashboard grey-and-blue — too clinical for a product about family and celebration.
3. Literal ethnic ornamentation (mandalas, filigree, saffron banners, khanda motifs) — reads as costume rather than considered design. Draws attention to itself instead of the users' photos, and any single symbol picks a lane the platform shouldn't pick.

**We commit to:**

- **A palette drawn from Punjabi and Rajasthani textile dyeing** — the two North Indian regional traditions with the strongest indigo-and-turmeric material history. Deep indigo (quiet, confident), turmeric (single high-energy accent), unbleached linen (paper-white background), tea-stained neutrals. Grounded in the community's own visual vernacular without being on-the-nose about any single religion or region.
- **Typography that carries confidence, not decoration** — one geometric sans (Inter Tight) for display, one system-stack fallback for body, one mono for data. No serifs. No script fonts. English-only UI for now; if Punjabi (Gurmukhi) or Hindi (Devanagari) rendering is added later, Noto Sans Gurmukhi / Noto Sans Devanagari would pair cleanly with Inter Tight at the same optical weights.
- **The signature moment is the slideshow itself** — the app's job is to make photos the star. Chrome recedes. Loading and transition moments echo the slideshow-fade aesthetic of the product's output.

---

## Color palette

All values also expressed as CSS custom properties in `starter_templates/input.css`.

### Primary palette

| Token | Hex | Role |
|---|---|---|
| `--color-ink` | `#1A1F36` | Primary text, active nav, headings. Never pure black — the near-black feels warmer. |
| `--color-ink-soft` | `#4A5170` | Secondary text, muted labels, disabled state. |
| `--color-ink-faint` | `#8A90A8` | Placeholder text, form hints, timestamps. |
| `--color-paper` | `#FBF9F4` | Page background. Unbleached linen tone — not white, not cream. |
| `--color-paper-raised` | `#FFFFFF` | Cards, modals, elevated surfaces. |
| `--color-line` | `#E8E4DA` | Borders, dividers, table rules. |
| `--color-line-soft` | `#F1EEE6` | Subtle backgrounds (striped rows, hover, subtle fills). |

### Accents

| Token | Hex | Role |
|---|---|---|
| `--color-indigo` | `#2E3271` | Primary action, links, focus rings. From Rajasthani indigo dye. |
| `--color-indigo-deep` | `#1F225A` | Hover state for indigo. |
| `--color-indigo-soft` | `#EEF0FA` | Selected row backgrounds, badge fills. |
| `--color-turmeric` | `#E5A63E` | The one high-energy accent. Reserved for celebratory moments (a completed render, a milestone reached). NOT used as a general CTA color — too loud. |
| `--color-turmeric-soft` | `#FAF0DA` | Warning-badge background, "pending" tag. |

### Status colors

| Token | Hex | Semantics |
|---|---|---|
| `--color-success` | `#2F7D4F` | Approvals, completed renders, active users. |
| `--color-success-soft` | `#E4F3EA` | Success badge background. |
| `--color-danger` | `#B23A48` | Destructive actions, errors, over-quota. |
| `--color-danger-soft` | `#F7E4E7` | Error banner background. |
| `--color-caution` | `#B4761F` | Pending-approval, near-quota, awaiting action. |
| `--color-caution-soft` | `--color-turmeric-soft` | Reused. |

### Dark mode

Dark mode is required. Every token has a `--dark-*` counterpart in `input.css`. Rule of thumb for translation:
- `--color-ink` becomes `--dark-color-ink: #F1EEE6` (the light `--color-line-soft`)
- `--color-paper` becomes `--dark-color-paper: #14162A`
- Accents stay saturated but shift slightly toward blue in dark mode (turmeric especially can look muddy on dark backgrounds — bump lightness).

Full dark-mode token table is in `starter_templates/input.css`. Toggle via `<html class="dark">`.

---

## Typography

### Fonts

- **Display / UI:** [Inter Tight](https://fonts.google.com/specimen/Inter+Tight) — variable font, weights 400/500/600/700. Self-hosted (see `starter_templates/README.md`).
- **Body fallback:** system-ui / -apple-system / Segoe UI / Roboto — kicks in if Inter Tight fails to load. On the same optical metrics, so no CLS jump.
- **Mono (data, code):** [JetBrains Mono](https://www.jetbrains.com/lp/mono/) — weights 400/500. Used for OTP codes, IDs, file names, timestamps in dense tables.

No serifs. Serifs signal "editorial" or "traditional" — neither fits a tool for community organizers.

### Type scale

Mobile-first. Sizes below are the mobile default; desktop bumps some (`.md:text-*` in Tailwind).

| Token | Mobile size / line | Desktop | Use |
|---|---|---|---|
| `text-display` | 32px / 40px | 40px / 48px | Page hero H1. Used sparingly. |
| `text-h1` | 24px / 32px | 28px / 36px | Section titles. |
| `text-h2` | 20px / 28px | 22px / 30px | Sub-section titles, card headers. |
| `text-h3` | 17px / 24px | 18px / 26px | List item titles. |
| `text-body` | 16px / 24px | 16px / 24px | Body copy. iOS-safe minimum for readable body. |
| `text-small` | 14px / 20px | 14px / 20px | Secondary content. |
| `text-caption` | 12px / 16px | 12px / 16px | Timestamps, labels, table cell metadata. |
| `text-micro` | 11px / 14px | 11px / 14px | Uppercase eyebrows, form hints. Tracked +0.02em. |

### Weight vocabulary

- **400** — body, secondary content
- **500** — button labels, table headers, active nav
- **600** — h2/h3 titles, emphasized inline text
- **700** — display, h1, numeric callouts

Never use 800/900. Feels aggressive against the warm palette.

---

## Spacing

Tailwind's default spacing scale, augmented with these named tokens:

| Token | Value | Use |
|---|---|---|
| `--space-hair` | 1px | Rule strokes |
| `--space-tight` | 4px | Icon-to-label gap |
| `--space-close` | 8px | Related elements |
| `--space-comfortable` | 16px | Default gap in flows |
| `--space-loose` | 24px | Between distinct groups |
| `--space-airy` | 40px | Between sections |
| `--space-open` | 64px | Above/below the hero |

**Mobile page padding:** 16px left/right, 20px top/bottom.
**Desktop page padding:** 32px left/right (or the sidebar takes 240px, content region gets 32px internal padding).

---

## Breakpoints

Tailwind-compatible.

| Name | Width | Devices | Layout implication |
|---|---|---|---|
| default (mobile) | 0–639px | Phones (iPhone SE = 375, iPhone 15 = 393) | Single column, bottom nav, cards |
| `sm:` | 640–767px | Large phones landscape, small tablets portrait | Still single column, larger padding |
| `md:` | 768–1023px | Tablets, small laptops | Two column, side sheet becomes sidebar |
| `lg:` | 1024–1279px | Standard desktop | Full sidebar, table view of lists |
| `xl:` | 1280px+ | Wide desktop | Reserved margins, denser tables |

**Layout switch points:**
- Bottom nav → sidebar at `md:` (768px)
- Card list → table view at `lg:` (1024px) — even at `md:`, tables are cramped
- Bottom sheet → modal dialog at `md:` (768px)

---

## Elevation

Three levels, no more.

| Token | Value | Use |
|---|---|---|
| `--shadow-flat` | none | Default. Most of the UI. |
| `--shadow-raise` | `0 1px 2px rgba(26,31,54,0.06), 0 4px 12px rgba(26,31,54,0.04)` | Cards, dropdowns |
| `--shadow-lift` | `0 4px 8px rgba(26,31,54,0.08), 0 16px 32px rgba(26,31,54,0.10)` | Modals, bottom sheets, popovers |

No neumorphic dual shadows. No glow effects. Elevation reads through darker tones of the same warm gray, never bluish.

---

## Border radius

- **`--radius-tight`: 4px** — badges, small tags, table cells
- **`--radius-standard`: 8px** — buttons, inputs, small cards
- **`--radius-comfortable`: 12px** — cards, modals
- **`--radius-round`: 9999px** — avatars, pill chips

Notably absent: 16px and 20px. Two radius steps that feel similar are one too many.

---

## Motion

Deliberate, restrained, and always respectful of `prefers-reduced-motion`.

### Durations

- **`--motion-quick`: 120ms** — hover states, focus rings, small color changes
- **`--motion-standard`: 200ms** — dropdowns, tab switches, badge state changes
- **`--motion-comfortable`: 320ms** — modals open/close, bottom sheets, page-level transitions
- **`--motion-slow`: 500ms** — the signature slideshow-photo transition, echoed in loading skeletons

### Easings

- **`--ease-standard`: `cubic-bezier(0.4, 0, 0.2, 1)`** — default for most transitions
- **`--ease-emphasized`: `cubic-bezier(0.32, 0.72, 0, 1)`** — bottom sheets and modals, slight overshoot feel

### Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

Applied globally. No exceptions.

---

## Component inventory

Every component needs a mobile and desktop rendering. Marked ✱ when the same visual works at both breakpoints.

### Foundational (build these first)

- ✱ **Button** — primary, secondary, ghost, destructive; three sizes; icon-only variant
- ✱ **Icon button** — 44px minimum tap target on mobile
- ✱ **Input** — text, email, password, tel, number, textarea; inline validation
- ✱ **Select** — native `<select>` on mobile (better UX), custom listbox on desktop only
- ✱ **Checkbox / Radio** — 24px hit area, 20px visual
- ✱ **Switch** — for boolean settings; visually different from checkbox
- ✱ **Badge** — role, status, count; five color variants
- ✱ **Avatar** — with initials fallback, 3 sizes (24, 32, 44)
- ✱ **Divider** — hairline horizontal rule
- ✱ **Spinner** — inline loading indicator
- ✱ **Skeleton** — placeholder for loading list items and cards
- ✱ **Toast** — bottom-anchored on mobile, top-right on desktop, auto-dismiss 5s, with undo action support

### Layout

- **Page shell** — header, main, optional nav; safe-area insets for iOS
- **Bottom nav** (mobile only) — 4–5 icons + labels
- **Sidebar** (desktop only) — collapsible, workspace switcher at top
- **Section** — h2 + optional description + content
- **Empty state** — icon, title, description, CTA

### Data display

- **Card** — the workhorse. Header, body, footer. Tap-anywhere-to-open pattern.
- **List item** — for dense lists (nav, settings)
- **Table** (desktop only) — `md:` and up. Below that, we render cards instead.
- **Key-value row** — for detail views
- **Progress bar** — for storage quotas and render progress
- **Stat card** — big number + label + trend

### Interactive

- **Modal** — centered dialog, desktop-primary
- **Bottom sheet** — slide-up from bottom, mobile-primary. Draggable dismiss.
- **Popover** — anchored to a trigger, for kebab menus on desktop
- **Dropdown** — for form-adjacent select-like patterns
- **Tabs** — segmented control on mobile, underline tabs on desktop
- **Search input** — with clear button, keyboard shortcut hint on desktop

### Feedback

- **Alert / callout** — inline info/warning/error/success block
- **Confirmation dialog** — for destructive actions, with typed confirmation for the truly dangerous
- **Undo toast** — for reversible actions (suspend, delete-with-grace)

### Domain-specific (Slideshow Studio)

- **User card** — the pilot component. See spec in `02_USERS_ADMIN_SPEC.md`.
- **Project card** — thumbnail grid, title, photo count, status
- **Photo tile** — square thumbnail, hover/tap for actions
- **Render status pill** — draft/rendering/rendered/failed with icon
- **Storage meter** — quota bar with used/available, warning threshold at 80%
- **OTP input** — 6 or 8 character segmented input, auto-advance, paste-friendly

---

## Iconography

**Library:** [Lucide](https://lucide.dev/) — MIT license, ~1500 icons, all consistent 24×24 with 2px stroke, inline SVG (no icon font). Free forever.

**Stroke weight:** 2px default. `stroke-current` in Tailwind picks up text color.

**Sizes used:**
- 16px — inline within text (Ctrl+K badge, "external link" hint)
- 20px — buttons, form field affix
- 24px — nav items, headers, list markers
- 28px — feature callouts (rare)

**No emoji as UI icons.** Emoji rendering varies too much across platforms. Emoji only appears in user-generated content (project names, notes).

---

## Content voice

Extracted from the frontend-design skill and tuned to the Slideshow Studio brief.

- **Second-person, active** — "Add photos" not "Photos can be added"
- **No apologies** — errors state what happened and what to do next
- **No filler** — remove "please", "just", "simply", "you can" wherever possible
- **Verbs match their outcome** — a button labeled "Publish" produces a toast that says "Published"
- **Sentence case everywhere** — never Title Case Buttons
- **Numbers as numerals in UI** — "3 projects", not "three projects"

**Empty state formula:**
1. Icon or subtle illustration
2. Short heading in active voice describing the state ("No projects yet")
3. One sentence explaining what to do next ("Create your first slideshow to get started")
4. Primary CTA button

---

## Accessibility floor (non-negotiable)

- **Color contrast** — every foreground/background pair meets WCAG AA (4.5:1 for body, 3:1 for large text). All tokens above verified.
- **Keyboard navigation** — every interactive element tab-focusable, focus ring always visible (never `outline: none` without a replacement).
- **Focus ring** — 2px `--color-indigo` outline offset by 2px. Applies to all focusable elements.
- **Tap targets** — 44×44px minimum on mobile (Apple HIG standard). Even for tightly-packed lists.
- **Screen reader labels** — every icon button has `aria-label`. Every form input has `<label>` (visible or `sr-only`).
- **Semantic HTML** — `<nav>`, `<main>`, `<article>`, `<button>` (never `<div onclick=…>`).
- **Motion respected** — `prefers-reduced-motion` disables all non-essential animations.
