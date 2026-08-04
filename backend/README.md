# HNBG Backend

FastAPI + Strawberry GraphQL + PostgreSQL backend for the HNBG Task
Management System. See [`../docs/BACKEND_ARCHITECTURE.md`](../docs/BACKEND_ARCHITECTURE.md)
for the full design (ERD, RBAC matrix, schema rationale) and
[`../docs/ORG_STRUCTURE.md`](../docs/ORG_STRUCTURE.md) for how the real
HNBG staff roster maps onto the schema.

> **Status:** working end to end — models, migrations, GraphQL
> resolvers, RBAC, and SMS/email notifications are all implemented and
> verified against a real running stack (Postgres + Redis + FastAPI +
> Celery via `docker-compose up`). What's *not* here yet: a self-serve
> signup flow (this is single-org, admin-provisioned — see
> `scripts/set_password.py`), `tests/`, and a frontend actually wired to
> this API instead of the static HTML prototypes in `../prototypes/`.

## Running everything in Docker (recommended)

```bash
cp .env.example .env   # fill in JWT_SECRET_KEY at minimum
docker-compose up --build
```

If your Docker install doesn't recognize `docker compose` (space) as a
subcommand, use the hyphenated `docker-compose` form shown above
instead — both do the same thing.

Then, in a separate terminal, apply the schema and load the real staff
roster:

```bash
docker-compose exec api alembic upgrade head
docker-compose exec api python scripts/seed_staff.py
```

GraphQL playground: http://localhost:8000/graphql — try `{ departments
{ id name } }` or `{ users { fullName jobTitle role } }` to confirm real
data comes back.

### Logging in

`seed_staff.py` deliberately leaves everyone's `password_hash` empty —
it populates the org chart, not login credentials. To give one person
login access:

```bash
docker-compose exec api python scripts/set_password.py <email> <password>
```

Then use GraphQL's `login(email, password)` mutation in the playground
to get a JWT, and send it back as `Authorization: Bearer <token>` on
subsequent requests to access anything behind `IsAuthenticated`.

Not everyone in the seeded roster has an email on file (several
restaurant-role staff don't — see `docs/ORG_STRUCTURE.md`), so pick one
that does, e.g. `mbdekkaido@gmail.com`.

## Local setup without Docker

```bash
cd backend
cp .env.example .env
# Edit .env: change DATABASE_URL/REDIS_URL hosts from `db`/`redis` to
# `localhost` — those service names only resolve inside the Compose
# network.
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

You'll still need Postgres and Redis running somewhere reachable at
`localhost` — e.g. `docker-compose up -d db redis` to start just those
two, then run the API/worker natively.

## Project layout

See the "Project layout" section in
[`../docs/BACKEND_ARCHITECTURE.md`](../docs/BACKEND_ARCHITECTURE.md#project-layout-backend).

## Remaining known gaps

1. No `tests/` yet (pytest + `httpx.AsyncClient` against the GraphQL
   endpoint would be the natural next step).
2. No self-serve signup/invite flow — `scripts/set_password.py` is the
   current admin-side workaround.
3. The prototypes in `../prototypes/` are still static HTML/CSS with
   hardcoded sample data — not yet wired to this API.
