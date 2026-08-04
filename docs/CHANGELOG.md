# Changelog

Design iteration history, most recent first. Dates reflect the session in
which each change was made.

## Unreleased

- Added `backend/` — FastAPI + Strawberry GraphQL + PostgreSQL scaffold
  matching `docs/BACKEND_ARCHITECTURE.md` (models, GraphQL schema/types,
  RBAC permission classes, JWT helpers, Docker Compose, Alembic setup).
  Verified the schema builds and all modules import cleanly; resolver
  bodies are intentionally left as `TODO`s for the implementation phase.
- **Locked** the frontend design phase — no further visual changes without explicit sign-off.
- Reorganized all deliverables into this git-ready repository structure.

## Create Task form

- Description field: increased line-height to `1.65`, added top padding,
  softened text color, added warm `--surface-alt` background wash + blue
  caret on focus for a calmer typing experience.
- Added a **Department** select field (Engineering, Product, Design,
  Marketing, Sales, Finance, Human Resources, IT & Operations), replacing
  the earlier **Project** field for now.
- Applied blue→red gradient borders to the field groups, dividers, and the
  priority segmented-control track.
- Rebuilt the form in the Apple HIG-inspired style (floating labels, grouped
  sections, segmented priority control, inline validation) — first as a
  standalone React component (`CreateTaskForm.jsx`), then ported the same
  pattern back into the plain-HTML `create-task.html` prototype so both stay
  visually identical.

## Branding

- Removed the baked-in white background from the HNBG logo (made
  transparent) and separately cropped out the tagline text so it could be
  reproduced as live, colorable HTML rather than a raster image.
- Added "Hokkaido Nepal Business Group" tagline as live text, colored to
  mirror the logo's own letter coloring (H/N in blue, B/G in red).
- Replaced "Task Management System" with a compact "HN·BG TMS" label,
  colored the same way.
- Rebranded the entire color system from generic Apple blue (`#0071e3`) to
  HNBG's own blue (`#1c4b96`) and red (`#e2231c`), including all avatar
  colors, buttons, links, and status indicators.

## Dashboard

- Simplified the front page down to four status tiles (Pending, In
  Progress, Overdue, Completed) plus a single Create New Task action,
  removing the earlier per-status ticket-preview panels.
- Introduced the volume-based severity color scale (blue → red) across the
  three active-work counts, with Completed pinned to green regardless of
  its count.
- Added soft-background pill styling to each status label, using the same
  per-card severity color for background/border/text.
- Removed the Projects/General sidebar sections to keep navigation focused.

## System-wide

- Applied gradient (blue→red) borders across every major container:
  sidebar edge, topbar underline, status cards, panels, tables and table
  rows, the task detail card, the login card, and the mobile nav/tab bars.

## Platform coverage

- Built the initial clickable web prototype: login, dashboard, task list,
  task detail, create task modal.
- Built iOS-style mobile prototype: Dashboard and My Tasks screens in a
  phone frame with status bar, large-title nav, and bottom tab bar.
