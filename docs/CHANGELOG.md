# Changelog

Design iteration history, most recent first. Dates reflect the session in
which each change was made.

## Unreleased

- Added the initial Alembic migration (`0001_initial_schema`), hand-
  written to mirror every model in `app/models/*.py` exactly (all 7
  tables, all 3 enum types, the `ticket_number_seq` sequence used for
  human-readable ticket numbers). Written by hand rather than
  `alembic revision --autogenerate` since no live Postgres instance was
  reachable in the environment this was built in — verified instead via
  `alembic upgrade head --sql` and `alembic downgrade base --sql`,
  confirming both directions render valid, correctly-ordered SQL with no
  errors. Also fixed `migrations/env.py`, which only imported
  `Comment, Department, Task, User` and was missing the newer `Branch`,
  `BusinessUnit`, and `NotificationLog` models — meant `alembic revision
  --autogenerate` would silently miss those 3 tables if run before this
  fix. Run `docker-compose exec api alembic upgrade head` (or `alembic
  upgrade head` locally) to apply it.
- Fixed a real runtime bug found while first booting the stack via
  `docker-compose up`: hitting `/graphql` returned a bare "Internal
  Server Error" with `strawberry.exceptions.InvalidCustomContext` in the
  API logs. Cause: `GraphQLContext` was a plain `@dataclass`, but
  Strawberry's FastAPI integration requires the context object to
  subclass `strawberry.fastapi.BaseContext` (or be a dict) — it calls
  `BaseContext.__init__()` expectations (`request`/`response`/
  `background_tasks` attrs) after construction. Fixed by making
  `GraphQLContext` a proper `BaseContext` subclass with an `__init__`
  that calls `super().__init__()`. Also fixed `.env.example`'s
  `DATABASE_URL`/`REDIS_URL` defaulting to `localhost`, which only works
  outside Docker — inside the `api`/`worker` containers those must be
  the Compose service names (`db`, `redis`), or the Celery worker can
  never reach Redis. Verified via `TestClient(app).get("/graphql")`
  returning 200 with the real GraphiQL page, reproducing the exact
  request path that failed in Docker.
- Implemented the GraphQL resolver logic that was previously left as
  `NotImplementedError` stubs: `login`/`refreshToken` (JWT issuing +
  password verification), `createTask`/`updateTask`/`assignTask`/
  `changeTaskStatus`/`deleteTask`/`addComment`, `updateNotificationPreferences`,
  and the `me`/`users`/`task`/`tasks`/`departments` queries (with RBAC
  department-scoping and cursor pagination on `tasks`). Added
  `app/graphql/mappers.py` (ORM → GraphQL type mapping),
  `app/graphql/errors.py` (typed `code`-bearing GraphQL errors), and
  `app/services/user_service.py`. `app/main.py`'s auth context now
  actually loads the requesting user from their JWT instead of leaving a
  TODO, and the DB session is now a proper FastAPI-managed dependency
  (closed automatically per request) instead of a manually opened one.
  `User.email` is now nullable end-to-end (GraphQL type + SDL) to match
  the seeded roster. Verified with a full create → update → assign →
  status-change → comment → delete flow against an isolated SQLite DB,
  not just import/compile checks.
- Seeded the real HNBG staff roster (39 people) into the backend:
  new `BusinessUnit` and `Branch` models (Business Unit → Branch → User),
  `branch_id`/`job_title` added to `User`, `email`/`password_hash` made
  nullable to allow org-chart-only entries without login access yet.
  Data + idempotent loader in `backend/seed_data/staff.json` /
  `backend/scripts/seed_staff.py`. Mapping rationale (job title →
  canonical department, job title → RBAC role, typo/data-quality fixes)
  documented in new `docs/ORG_STRUCTURE.md`; ERD in
  `docs/BACKEND_ARCHITECTURE.md` updated accordingly.
- Added SMS (Twilio) + email (SMTP) notifications for HIGH/URGENT
  priority tickets: `NotificationLog` model, `notifications.py` service
  (recipient resolution, send + audit logging, Celery task with retries),
  `phone_number`/`notify_email`/`notify_sms` fields on `User`,
  `updateNotificationPreferences` GraphQL mutation, and
  `NOTIFY_PRIORITIES`/`SMTP_*`/`TWILIO_*` settings. Documented in
  `docs/BACKEND_ARCHITECTURE.md` (new Notifications section + updated ERD).
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
