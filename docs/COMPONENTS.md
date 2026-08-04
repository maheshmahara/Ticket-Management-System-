# Component Inventory

Reference for anyone porting these prototypes into a real frontend
framework. Class names refer to `prototypes/web/styles.css` unless noted.

## Layout shell

| Component | Class | Notes |
|---|---|---|
| App shell | `.app-shell` | Flex row: sidebar + main column |
| Sidebar | `.sidebar` | Sticky, blurred, gradient right border, brand + nav + user chip |
| Brand block | `.brand`, `.brand-logo`, `.brand-tagline`, `.brand-subtitle` | Logo (`hnbg-mark.png`) + colored tagline + "HN·BG TMS" label |
| Nav item | `.nav-item` (`.active` modifier) | Sidebar links, active state uses accent-soft background |
| Topbar | `.topbar` | Sticky, blurred, gradient bottom border, search + actions |
| Search box | `.search-box` | Pill input, focus ring in accent blue |

## Dashboard

| Component | Class | Notes |
|---|---|---|
| Status card | `.status-card` | 4-up grid: Overdue / In Progress / Pending / Completed, severity-colored (see Design System) |
| Severity bar | `.severity-bar` | 4px top accent strip, color via `--sev-color` custom property set inline per card |
| Status label pill | `.status-label` | Soft-background pill using `--sev-bg` / `--sev-border` / `--sev-color` |
| Create Task CTA | `.btn.btn-primary.btn-lg` | Full-width primary button on the dashboard front page |
| Panel (ticket preview) | `.panel`, `.ticket-row` | Used on `task-detail.html` sidebar; general-purpose bordered list container |

## Task list (`tasks.html`)

| Component | Class | Notes |
|---|---|---|
| Filter pills | `.pill` (`.active`) | Status filter row |
| View toggle | `.view-toggle` | List/Board switch (Board view not yet built) |
| Table panel | `.table-panel`, `.table-head`, `.table-row` | Gradient-bordered table, per-row status chip, priority tag, assignee avatar |
| Status chip | `.status-chip` (`.pending` `.progress` `.review` `.done`) | Colored pill per task status |
| Priority tag | `.priority-tag` (`.priority-high` `.priority-medium` `.priority-low`) | Colored pill per priority |

## Task detail (`task-detail.html`)

| Component | Class | Notes |
|---|---|---|
| Detail main | `.detail-main` | Gradient-bordered content card: title, description, activity/comments |
| Detail side panel | `.detail-side .panel`, `.side-block` | Assignee, priority, due date, project, reporter metadata |
| Comment | `.comment` | Avatar + timestamped note |

## Create Task form (`create-task.html`, mirrored in `CreateTaskForm.jsx`)

| Component | Class (HTML) | React equivalent |
|---|---|---|
| Header | `.aform-header`, `.aform-icon`, `.aform-title`, `.aform-subtitle` | `<header>` block in JSX |
| Field group | `.aform-group` | `<fieldset>` |
| Floating text field | `.aform-field` + `<label>` sibling | `peer` + `peer-focus` Tailwind classes |
| Static (select/date) field | `.aform-field.is-static` | Pinned `<label>`, no peer animation |
| Inline error | `.aform-error` | Red `AlertCircle` message under Title |
| Priority segmented control | `.aform-priority`, `button.active` | `role="radiogroup"` buttons, `PRIORITIES` array |
| Assignee row | `.aform-assignee`, `.aform-assignee-avatar` | Avatar color/initials driven by `ASSIGNEES` array |
| Footer actions | `.aform-footer` | Cancel (ghost) / Create Task (primary, disabled while submitting) |

**Validation behavior:** Task Title is required. On blur or submit attempt,
an empty title shows a red inline error and focuses the field; the field's
bottom border and label switch from blue to red (`.error` state).

## Mobile (`prototypes/mobile/mobile-app.html`)

| Component | Class | Notes |
|---|---|---|
| Phone frame | `.phone`, `.notch`, `.home-indicator` | Device chrome for the prototype screenshots |
| Status bar / nav bar | `.status-bar`, `.ios-navbar`, `.ios-large-title` | iOS-style large-title header |
| Stat tile grid | `.mstat-grid`, `.mstat-tile` | 2×2 severity-colored stat cards (same scale as web dashboard) |
| Task card | `.mtask-card`, `.mtag` | Compact list item for My Tasks screen |
| Tab bar | `.tab-bar`, `.tab-item`, `.tab-fab` | Bottom navigation with floating create-task button |

## Buttons

| Class | Usage |
|---|---|
| `.btn.btn-primary` | Primary action (accent blue fill) |
| `.btn.btn-secondary` | Secondary action (neutral fill) |
| `.btn.btn-ghost` | Tertiary/text-style action |
| `.btn-lg` | Larger padding variant |
