# Design System

All tokens live in [`prototypes/web/styles.css`](../prototypes/web/styles.css)
as CSS custom properties on `:root`, and are mirrored where needed in
[`prototypes/mobile/mobile.css`](../prototypes/mobile/mobile.css) and inline
Tailwind classes (incl. `dark:` variants) in
[`components/react/CreateTaskForm.jsx`](../components/react/CreateTaskForm.jsx).

## Apple Design Resources this system is built on

- **San Francisco (SF Pro)** system-font stack, via `-apple-system` /
  `BlinkMacSystemFont`.
- **SF Symbols–style iconography** — regular-weight (stroke ≈ 2px), rounded
  line icons throughout nav, topbar, and status affordances.
- **Apple System Colors** — the brand palette below is expressed as a real
  light/dark *pair* per color, the same way Apple's own systemBlue /
  systemRed / etc. tables work (e.g. systemBlue `#007AFF` light →
  `#0A84FF` dark), not a single hex inverted at runtime.
- **Apple System Fill Colors** — neutral hover/pressed/track surfaces use
  the four-step `systemFill` hierarchy (`--fill-1`…`--fill-4`,
  `rgba(120,120,128, .08/.12/.16/.2)` light, doubled-up alpha in dark)
  instead of ad hoc black/white tints.
- **macOS/iOS vibrancy materials** — sidebar, topbar, and the mobile nav/tab
  bars use `saturate(180%) blur(20px)` over a translucent fill, matching
  native chrome rather than a flat blur.
- **Full light/dark mode** via `prefers-color-scheme`, with an explicit
  `data-theme="dark"|"light"` override hook for manual toggles.

The one deliberate departure from strict restraint: the earlier
decorative dual-tone (blue→red) gradient border that used to outline
*every* card, table, and divider has been replaced with Apple's plain
hairline everywhere except the two places a brand mark actually belongs —
the login card's top edge and the monogram/avatar fills themselves.

## Brand colors

Sourced directly from the HNBG logo (`assets/branding/hnbg-logo-original.jpg`).
Each has a dark-mode value tuned the way Apple tunes its own system
colors for dark appearance (brighter, slightly desaturated) — see the
`@media (prefers-color-scheme: dark)` block in `styles.css`.

| Token | Light | Dark | Usage |
|---|---|---|---|
| `--accent` (HNBG Blue) | `#1c4b96` | `#4c8bdf` | Primary actions, links, focus states, "H" and "N" in logo |
| `--accent-hover` | `#163c78` | `#6ea3e8` | Primary button hover |
| `--danger` (HNBG Red) | `#e2231c` | `#ff453a` | Errors, overdue/high-severity states, "B" and "G" in logo |
| `--success` | `#1db954` | `#32d74b` | Completed status (fixed — not part of the severity scale) |
| `--warning` | `#f2a900` | `#ff9f0a` | Medium priority |
| `--neutral` | `#8e8e93` | `#98989d` | Low priority, unassigned states |

## System Fill Colors (neutral surfaces)

Apple's `systemFill` hierarchy, adopted verbatim, used for hover states,
segmented-control tracks, badge backgrounds, and anywhere a flat black/white
tint was previously hardcoded:

| Token | Light | Dark |
|---|---|---|
| `--fill-1` (quaternary) | `rgba(120,120,128,.08)` | `rgba(120,120,128,.18)` |
| `--fill-2` (tertiary) | `rgba(120,120,128,.12)` | `rgba(120,120,128,.24)` |
| `--fill-3` (secondary) | `rgba(120,120,128,.16)` | `rgba(120,120,128,.32)` |
| `--fill-4` (primary) | `rgba(120,120,128,.2)` | `rgba(120,120,128,.4)` |

### Severity scale (dashboard stat cards)

Card label/icon/border color is computed on a **blue → red gradient** by
relative volume among the three active-work counts (Overdue, In Progress,
Pending) — low count reads calm blue, high count reads urgent red.
**Completed is always green**, regardless of its count, since a high
completed count is a good thing, not a warning.

| Metric | Example count | Color |
|---|---|---|
| Overdue (lowest) | 14 | `#1c4b96` (pure blue) |
| In Progress (mid) | 64 | `#733960` (blue/red blend) |
| Pending (highest) | 128 | `#e2231c` (pure red) |
| Completed | 341 | `#1db954` (always green) |

### Borders

Cards, panels, tables, sidebar, and topbar borders are a plain 1px
`--border` hairline — Apple's own restraint, not a decorative gradient.
The HNBG blue→red gradient survives in exactly two places, both of which
are legitimately "the brand mark" rather than chrome: the login card's
3px top edge (`border-image: linear-gradient(90deg, #1c4b96, #e2231c)`)
and the monogram/avatar circle fills (`linear-gradient(135deg, #1c4b96,
#e2231c)`).

## Neutral palette

| Token | Light | Dark |
|---|---|---|
| `--bg` | `#f5f5f7` | `#000000` |
| `--surface` | `#ffffff` | `#1c1c1e` |
| `--surface-alt` | `#fbfbfd` | `#232326` |
| `--text-primary` | `#1d1d1f` | `#f5f5f7` |
| `--text-secondary` | `#6e6e73` | `#98989d` |
| `--text-tertiary` | `#86868b` | `#6e6e73` |
| `--border` | `rgba(0,0,0,.09)` | `rgba(255,255,255,.1)` |
| `--border-strong` | `rgba(0,0,0,.14)` | `rgba(255,255,255,.16)` |
| `--sidebar-bg` / `--topbar-bg` | translucent white/off-white | translucent near-black |

See [System Fill Colors](#system-fill-colors-neutral-surfaces) above for
the hover/pressed-state tokens.

## Typography

System font stack (Apple HIG-style):

```css
-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", "Helvetica Neue", Arial, sans-serif;
```

Base size `15px`, line-height `1.47`. Form body text uses `1.65` line-height
for a more comfortable, "warm" reading feel in longer fields like Description.

## Shape & elevation

| Token | Value |
|---|---|
| `--radius-sm` | `10px` |
| `--radius-md` | `16px` |
| `--radius-lg` | `22px` |
| `--radius-pill` | `999px` |
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,.04), 0 1px 1px rgba(0,0,0,.03)` |
| `--shadow-md` | `0 4px 16px rgba(0,0,0,.06), 0 1px 3px rgba(0,0,0,.04)` |
| `--shadow-lg` | `0 12px 40px rgba(0,0,0,.10), 0 2px 8px rgba(0,0,0,.04)` |

## Logo usage

- `assets/branding/hnbg-logo-original.jpg` — full logo with tagline, white background (source file, not for UI use directly).
- `assets/branding/hnbg-logo-transparent.png` — full logo, background removed.
- `assets/branding/hnbg-mark.png` — **cropped monogram only** (no tagline baked in). This is the version used across the product UI; the tagline ("Hokkaido Nepal Business Group") is reproduced as live, colored text in HTML/CSS instead, so it can be styled and localized independently of the image.

## Floating-label form pattern

Used in the Create Task form (`prototypes/web/create-task.html` and
`components/react/CreateTaskForm.jsx`):

- Text inputs/textareas: label starts in-place, animates to a small
  `11px` blue label on focus or when filled (CSS `:not(:placeholder-shown)` /
  Tailwind `peer` variants).
- Select/date fields: label is permanently pinned small at the top (no
  animation — selects always have a value).
- Focused field gets a warm `--surface-alt` background wash and a bottom
  accent line (blue normally, red if the field is in an error state).

`CreateTaskForm.jsx` mirrors the CSS tokens as literal Tailwind arbitrary
values plus a `dark:` variant on every color-bearing class (background,
border, text, focus/hover/active states) — including the priority
segmented control and assignee avatar palette, which were re-pointed from
generic blues/reds to the exact brand + system-fill hex values used
everywhere else. It has no build step of its own; `create-task-preview.html`
fetches the `.jsx` source directly and transpiles only the JSX with Babel,
so the preview can never drift from the production component.
