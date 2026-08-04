# Design System

All tokens live in [`prototypes/web/styles.css`](../prototypes/web/styles.css)
as CSS custom properties on `:root`, and are mirrored where needed in
[`prototypes/mobile/mobile.css`](../prototypes/mobile/mobile.css) and inline
Tailwind classes in [`components/react/CreateTaskForm.jsx`](../components/react/CreateTaskForm.jsx).

## Brand colors

Sourced directly from the HNBG logo (`assets/branding/hnbg-logo-original.jpg`).

| Token | Hex | Usage |
|---|---|---|
| `--accent` (HNBG Blue) | `#1c4b96` | Primary actions, links, focus states, "H" and "N" in logo |
| `--accent-hover` | `#163c78` | Primary button hover |
| `--danger` (HNBG Red) | `#e2231c` | Errors, overdue/high-severity states, "B" and "G" in logo |
| `--success` | `#1db954` | Completed status (fixed — not part of the severity scale) |
| `--warning` | `#f2a900` | Medium priority |
| `--neutral` | `#8e8e93` | Low priority, unassigned states |

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

### Gradient borders

Cards, panels, tables, sidebar, and topbar borders use a diagonal or
horizontal `linear-gradient(#1c4b96 → #e2231c)` instead of flat gray, applied
via the `background: … padding-box, gradient … border-box` CSS technique so
gradients respect `border-radius`. Alpha is tuned down (`0.2`–`0.5`) on line
dividers so dense areas (tables) don't feel noisy.

## Neutral palette

| Token | Hex |
|---|---|
| `--bg` | `#f5f5f7` |
| `--surface` | `#ffffff` |
| `--surface-alt` | `#fbfbfd` |
| `--text-primary` | `#1d1d1f` |
| `--text-secondary` | `#6e6e73` |
| `--text-tertiary` | `#86868b` |
| `--border` | `rgba(0,0,0,0.08)` |
| `--border-strong` | `rgba(0,0,0,0.12)` |

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
