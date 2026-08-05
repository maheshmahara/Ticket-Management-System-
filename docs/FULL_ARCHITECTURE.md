# HNBG Task Management System — Full Architecture

This document describes the system as it actually exists in the codebase today — not the original design intent, which drifted in places as real bugs were found and fixed. It supersedes nothing (`BACKEND_ARCHITECTURE.md`, `ORG_STRUCTURE.md`, and `CHANGELOG.md` remain the detailed change-by-change record), but it's the single place to read to understand how every piece fits together.

## 1. Tech stack

| Layer | Technology |
|---|---|
| Frontend | Static HTML/CSS/vanilla JS, no build step, no framework |
| API | FastAPI + Strawberry GraphQL (single `/graphql` endpoint) |
| ORM | SQLAlchemy 2.0, fully async (`asyncpg` driver) |
| Database | PostgreSQL 15 |
| Background jobs | Celery, Redis as broker + result backend |
| Auth | JWT (access + refresh tokens), `python-jose` + `passlib[bcrypt]` |
| Migrations | Alembic |
| Notifications | SMTP (email) + Twilio (SMS) |
| Local orchestration | Docker Compose (4 services: `db`, `redis`, `api`, `worker`) |

## 2. High-level architecture

```
┌─────────────────────────────┐
│  prototypes/web/*.html       │   Static pages, served by any HTTP
│  + js/api.js, js/admin.js    │   static file server (e.g. python -m
│                              │   http.server). No build tooling.
└──────────────┬───────────────┘
               │ fetch() → POST /graphql, JWT in Authorization header
               ▼
┌─────────────────────────────┐
│  FastAPI app (app/main.py)   │
│  ├─ CORS middleware          │
│  ├─ GraphQLRouter            │◄── strawberry.fastapi
│  │   context_getter:         │      decodes JWT → loads User → attaches
│  │   GraphQLContext(db,user) │      db session (per-request) + user
│  └─ GET /health              │
└──────────────┬───────────────┘
               │
   ┌───────────┼─────────────────────────┐
   ▼                                     ▼
┌────────────────────┐         ┌──────────────────────┐
│ app/graphql/        │         │ app/services/          │
│  queries.py         │────────▶│  task_service.py       │
│  mutations.py       │  calls  │  org_service.py        │
│  permissions.py     │         │  user_service.py       │
│  mappers.py         │         │  notifications.py       │
│  types.py           │         └───────────┬──────────┘
└────────────────────┘                     │
                                             ▼
                                  ┌──────────────────────┐
                                  │ app/models/*.py       │  SQLAlchemy ORM
                                  │ (7 tables)             │
                                  └───────────┬──────────┘
                                             ▼
                                  ┌──────────────────────┐
                                  │ PostgreSQL             │
                                  └──────────────────────┘

Celery worker (separate container, same image):
  notifications.send_task_notifications  ← enqueued by task_service.py
  after create/assign/priority-escalate, if priority is high/urgent.
  Redis is both the broker and the result backend.
```

Every mutation follows the same shape: a thin resolver in `mutations.py` authenticates/authorizes (via `permission_classes` and, for object-level checks, `can_edit_task`/`can_view_task`), delegates the actual work to a function in `app/services/*.py`, and maps the returned ORM row to a GraphQL type via `app/graphql/mappers.py`. Query resolvers in `queries.py` follow the same pattern minus the "delegate to a service" step for simple reads.

## 3. Repository layout

```
hnbg-task-management/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app, GraphQL context, CORS, /health
│   │   ├── core/                config.py (env settings), database.py (engine/Base),
│   │   │                        security.py (JWT + bcrypt), celery_app.py
│   │   ├── models/               7 SQLAlchemy models (see §4)
│   │   ├── graphql/               types.py, queries.py, mutations.py,
│   │   │                         permissions.py, mappers.py, errors.py, schema.py
│   │   └── services/              task_service.py, org_service.py, user_service.py,
│   │                              notifications.py — all business logic
│   ├── migrations/                Alembic (one hand-written initial migration)
│   ├── scripts/                   seed_staff.py, set_password.py
│   ├── seed_data/staff.json       Real HNBG roster (39 people)
│   ├── docker-compose.yml         db, redis, api, worker
│   └── Dockerfile                 shared image for api + worker
├── prototypes/
│   ├── web/                       index (login), dashboard, tasks, task-detail,
│   │                              create-task, admin — the actual working app
│   │   └── js/api.js, js/admin.js
│   └── mobile/                    Static iOS-style mockup, not wired to the API
├── components/react/              One-off React component preview (Create Task),
│                                   not part of the live app
└── docs/                          This file + BACKEND_ARCHITECTURE, ORG_STRUCTURE,
                                    CHANGELOG, DESIGN_SYSTEM, COMPONENTS, PROJECT_STRUCTURE
```

## 4. Data model

Seven tables, all UUID-keyed:

**BusinessUnit** → **Branch** → **User** ← **Department** (a user belongs to exactly one Department *and* optionally one Branch — these are two independent, non-nested groupings that both landed on `User`, for reasons explained in `ORG_STRUCTURE.md`: Department is the original flat grouping the schema shipped with; BusinessUnit/Branch were added later to represent HNBG's real reporting lines — "Overall" / "Restaurants" / "Trading" business units, each containing physical branches like "Headoffice" or "Hokkaido Sora" — once the real staff roster needed importing. A user's Department drives task RBAC (§5); Branch is informational/org-chart data today and isn't yet used in any permission check.)

**Task** is the core entity: belongs to one Department, has an optional Assignee and a required Reporter (both Users), a status (`PENDING → IN_PROGRESS → REVIEW → DONE`), a priority (`LOW/MEDIUM/HIGH/URGENT`), and an optional `due_at`. `is_overdue` is computed, not stored (`due_at` in the past and status isn't `DONE`) — deliberately, to avoid a background job having to mutate every row when a deadline passes. Every `datetime` column across every model is timezone-aware (`TIMESTAMPTZ`), enforced globally via `Base.type_annotation_map` in `database.py`, after naive-vs-aware mismatches caused two separate real bugs (task creation, and the `is_overdue` property itself) earlier in this project.

**Comment** belongs to one Task and one author (User).

**NotificationLog** is an audit trail: one row per email/SMS *attempt* (not per notification decision), recording channel, trigger, status (`QUEUED/SENT/FAILED`), and the provider's message ID or error text. Written by `notifications.py`, not yet read anywhere in the UI (a natural next admin-panel addition).

All three-way enum columns (`User.role`, `Task.status`, `Task.priority`, `NotificationLog.channel/trigger/status`) use `values_callable` so SQLAlchemy binds by the enum's lowercase `.value` rather than its uppercase Python member name — Postgres's enum types were created with the lowercase strings, and this mismatch was a real bug caught only by actually seeding data against Postgres.

## 5. Authentication & RBAC

**Auth**: `login(email, password)` returns a short-lived access token (30 min) and a longer-lived refresh token (14 days), both JWTs signed with `JWT_SECRET_KEY`. Every subsequent GraphQL request sends the access token as `Authorization: Bearer <token>`; `app/main.py`'s `get_context` decodes it, loads the User by the `sub` claim, and attaches it to `info.context.user` (or leaves it `None` for an invalid/expired/missing token — resolvers gated with `IsAuthenticated` then reject the request).

**Roles**: `ADMIN`, `MANAGER`, `MEMBER` — a flat three-tier system, not a permissions matrix with individually toggleable capabilities.

**Task visibility** (`can_view_task` in `permissions.py`) and the `tasks` list query: Admins see everything, everyone else sees their own department's tasks *plus* any task assigned to or reported by them regardless of department (this second clause was added after a real bug: a task filed under Marketing but assigned to a Finance-department user was invisible to that person everywhere in the app, since the original logic only checked department). `dashboard_stats` applies the identical scoping so its tiles never disagree with what "My Tasks" actually lists.

**Task editing** (`can_edit_task`): Admin can edit anything; Manager can edit anything in their own department; Member can edit only a task they're the assignee or reporter of. `assignTask` adds one more rule on top: a Member can only assign a task to *themselves* — reassigning to someone else requires Manager or Admin.

**Admin-only actions** (`permission_classes=[IsAdmin]`): every mutation under the admin panel — creating/editing users, resetting passwords, and all Department/BusinessUnit/Branch CRUD — plus the `businessUnits` query. `IsAdmin` additionally blocks an admin from deactivating or demoting their own account via `updateUser`, since that would be an unrecoverable lockout with no other path back into the admin panel.

One structural note: Strawberry's `BasePermission` classes don't attach a GraphQL error `code` extension unless you set `error_extensions` explicitly. All three permission classes (`IsAuthenticated`, `IsAdmin`, `IsManagerOrAdmin`) now set `error_extensions = {"code": "FORBIDDEN"}` — without this, the frontend's `err.code === "FORBIDDEN"` checks (used everywhere to bounce an expired session back to login) silently never matched anything. (`IsManagerOrAdmin` is defined but not currently applied to any resolver — a placeholder for the day something needs "Manager or Admin, but not plain Member" gating that isn't already covered by `can_edit_task`'s object-level check.)

## 6. GraphQL API surface

**Queries**: `me`, `dashboardStats`, `departments`, `businessUnits` (admin-only), `users(departmentId)`, `task(id)`, `tasks(filter, sort, page)`.

**Mutations — auth**: `login`, `refreshToken`.

**Mutations — tasks**: `createTask`, `updateTask`, `assignTask`, `changeTaskStatus`, `deleteTask`, `addComment`.

**Mutations — self-service**: `updateNotificationPreferences` (a user's own email/SMS opt-in + phone number).

**Mutations — admin**: `createDepartment`, `createBusinessUnit`, `createBranch`, `updateBranch`, `createUser`, `updateUser`, `resetUserPassword`.

`tasks` is cursor-paginated (base64-encoded offset cursors) and supports filtering by status, priority, department, assignee, free-text search on title, and an `excludeDone` flag (used by the "My Tasks" sidebar badge to count only outstanding work).

## 7. Task lifecycle

A task is created via `createTask` (title, department, priority, optional description/due date/assignee) — the reporter is always the creating user, ticket numbers come from a Postgres sequence formatted as `TCK-0001`, `TCK-0002`, etc. From there:

- **Status** moves `PENDING → IN_PROGRESS → REVIEW → DONE` via `changeTaskStatus` — this is the "close a ticket" action, gated by `can_edit_task`. Moving to `DONE` stamps `completed_at`; moving away from `DONE` clears it.
- **Assignment** changes via `assignTask`, gated by `can_edit_task` plus the Member-self-only rule above.
- **Comments** are append-only via `addComment`, gated by `can_view_task` (if you can see the task, you can comment on it).

The task-detail page (`prototypes/web/task-detail.html`) is the only place these last two actions are currently exposed in the UI — this was a real gap (the mutations existed long before any page called them) fixed after the fact.

## 8. Notifications

High/urgent-priority tasks trigger SMS + email to the assignee (and, for URGENT specifically, the department's managers/admins too) on three events: creation, assignment, and priority escalation into HIGH/URGENT. The decision to enqueue happens synchronously in `task_service.py` (`enqueue_if_needed`), but the actual send happens in a Celery task (`send_task_notifications`) — never inline in a resolver, so a slow or down email/SMS provider can never make a `createTask`/`updateTask` mutation hang or fail. Each attempt is logged to `NotificationLog` before sending (`QUEUED`) and updated after (`SENT`/`FAILED`), so retries can't silently double-send and failures are auditable.

Which priorities trigger a notification at all (`NOTIFY_PRIORITIES`), plus the SMTP/Twilio credentials, are environment-variable configuration today — not editable from the admin panel. Per-user opt-in (`notifyEmail`/`notifySms` + phone number) *is* editable, both by the user themselves (`updateNotificationPreferences`) and by an admin (`updateUser`, with the same "SMS requires a phone on file" guard applied in both places). Making the org-wide priority config live-editable would need a persisted settings table and a change to the currently-synchronous `should_notify()` — deliberately left as a documented gap rather than a half-verified change (see `CHANGELOG.md`).

There's also a `celery_app.py` beat schedule entry for a daily 8am `send_overdue_digest` task — it isn't implemented yet (the function doesn't exist), so the scheduled job will currently fail if Celery Beat is ever actually run.

## 9. Admin panel

`prototypes/web/admin.html` + `js/admin.js`, visible only to `role === 'ADMIN'` (both a client-side redirect and, more importantly, server-side `IsAdmin` gating on every call it makes). Three tabs:

- **Users** — staff directory, add/edit user (role, department, branch, job title, phone, active toggle), reset password.
- **Org Structure** — Departments (flat list + add), Business Units shown as expandable cards listing their Branches, with add/edit forms for both.
- **Notifications** — explains the environment-variable scope note from §8, and exposes per-user email/SMS toggles (SMS disabled client-side when there's no phone on file).

## 10. Frontend architecture

No framework, no build step, no bundler — plain `fetch()`-based GraphQL calls from inline `<script>` tags (or `js/api.js`/`js/admin.js` for the two larger pages). `js/api.js` is the single shared client: it holds the JWT in `localStorage`, exposes one function per GraphQL operation (`Api.createTask`, `Api.tasks`, etc.), throws a typed `Error` with `.code` set from the response's error `extensions.code` on failure, and exports shared render helpers (`STATUS_CLASS`, `formatDueDate`, `avatarInitials`, etc.) so every page's dynamically-rendered HTML uses the exact same CSS classes as the original static mockups. Every page except `index.html` (login) calls `requireAuth()` at the top, which redirects to login if there's no token on file — a fast client-side guard, not a substitute for server-side enforcement.

Pages: `index.html` (login), `dashboard.html` (status tiles), `tasks.html` (filterable list, "My Tasks"), `task-detail.html` (full task view + status/assignee controls + comments), `create-task.html` (new task form), `admin.html` (§9). `prototypes/mobile/` is a separate static iOS-style mockup that was never wired to the real API — visual reference only.

## 11. Deployment / local infra

Four Docker Compose services in `backend/docker-compose.yml`: `db` (Postgres, port 5432 published), `redis` (port 6379 published), `api` (Uvicorn with `--reload`, port 8000), `worker` (Celery worker, same image as `api`). `api` and `worker` both live-mount `./app`, `./scripts`, `./migrations`, `./seed_data`, and `./alembic.ini` from the host into the container — meaning any edit to those paths on disk takes effect on a container **restart**, with no rebuild needed; a rebuild is only required for `requirements.txt` or `Dockerfile` changes. Database schema is managed by a single hand-written Alembic migration (`0001_initial_schema.py`); the real 39-person HNBG roster is seeded via `scripts/seed_staff.py` from `seed_data/staff.json`, and initial passwords are set one-by-one via `scripts/set_password.py` (there's no self-service signup or email-invite flow).

The frontend has no server component at all — any static file server works (`python3 -m http.server` is what's been used throughout this project); its origin just needs to be in the API's `CORS_ORIGINS` setting.

## 12. Known gaps

Pulled together from `backend/README.md`, `BACKEND_ARCHITECTURE.md`'s open questions, and this session's work — kept honest rather than glossed over:

- No automated test suite (`pytest`) — every fix in this project so far has been verified manually, either against the user's live Docker stack or an isolated in-memory SQLite/schema-execute harness in the sandbox.
- No signup/invite flow — every account is created by an admin (via the admin panel or `scripts/`) with a password the admin sets directly.
- File attachments on tasks/comments are out of scope for v1.
- No in-app (bell icon) notification center — SMS + email only.
- `send_overdue_digest` is scheduled in Celery Beat but not implemented.
- Org-wide notification-priority config (which priorities alert, SMTP/Twilio secrets) is environment-variable-only, not admin-panel-editable.
- `NotificationLog` (the send audit trail) isn't surfaced in any UI yet.
- `Branch` is informational only — it doesn't yet factor into any RBAC check, unlike `Department`.
- The UI doesn't hide status/assignee controls from people who can't use them (per `can_edit_task`) — it shows them to anyone who can *view* the task and surfaces the resulting permission error on click, rather than duplicating the permission logic client-side or adding a `canEdit` field to `Task`.
