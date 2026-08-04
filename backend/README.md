# HNBG Backend

FastAPI + Strawberry GraphQL + PostgreSQL backend for the HNBG Task
Management System. See [`../docs/BACKEND_ARCHITECTURE.md`](../docs/BACKEND_ARCHITECTURE.md)
for the full design (ERD, RBAC matrix, schema rationale).

> **Status:** scaffold only. Models, GraphQL types, and resolvers here are
> structural stubs matching the design doc — implement the TODOs before
> treating this as a working API.

## Local setup

```bash
cd backend
cp .env.example .env          # fill in real values
docker compose up -d db redis # start Postgres + Redis
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head           # once migrations exist
uvicorn app.main:app --reload
```

GraphQL playground: http://localhost:8000/graphql

## Running everything in Docker

```bash
docker compose up --build
```

## Project layout

See the "Project layout" section in
[`../docs/BACKEND_ARCHITECTURE.md`](../docs/BACKEND_ARCHITECTURE.md#project-layout-backend).

## Next implementation steps

1. Flesh out SQLAlchemy models in `app/models/` (currently field stubs).
2. Implement Alembic migration for the initial schema.
3. Implement `app/core/security.py` (JWT issue/verify, password hashing).
4. Implement `app/graphql/permissions.py` RBAC checks per the matrix in
   the design doc.
5. Implement resolvers in `app/graphql/queries.py` / `mutations.py`.
6. Write `tests/` (pytest + `httpx.AsyncClient` against the GraphQL endpoint).
