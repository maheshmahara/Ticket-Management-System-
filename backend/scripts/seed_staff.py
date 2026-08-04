"""
Seeds the real HNBG staff roster (backend/seed_data/staff.json) into
BusinessUnit, Branch, Department, and User.

Idempotent: re-running does not create duplicates. Matching is by
`name` for BusinessUnit/Branch/Department, and by `full_name` + `branch`
for User (there's no reliable natural key otherwise, since many rows
have no email).

Seeded users get no password_hash (nullable — see app/models/user.py)
and cannot log in until an admin sets one via a future
"invite user" / "set password" flow. This script only establishes who
exists in the org chart; it does not grant login access.

Usage:
    cd backend
    python scripts/seed_staff.py

Requires DATABASE_URL / JWT_SECRET_KEY to be set (see .env.example) and
the DB schema to already be migrated (`alembic upgrade head`).
"""

import asyncio
import json
import sys
from pathlib import Path

# Running `python scripts/seed_staff.py` only puts this file's own
# directory (scripts/) on sys.path, not backend/ itself — so the `app`
# package below can't be found regardless of cwd or PYTHONPATH. Insert
# backend/ (this file's parent's parent) explicitly so the script works
# however it's invoked, e.g. `docker-compose exec api python
# scripts/seed_staff.py` with WORKDIR /app.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models import Branch, BusinessUnit, Department, User  # noqa: E402
from app.models.user import Role  # noqa: E402

SEED_FILE = Path(__file__).resolve().parent.parent / "seed_data" / "staff.json"


async def _get_or_create(db: AsyncSession, model, *, name: str, **extra):
    result = await db.execute(select(model).where(model.name == name))
    obj = result.scalar_one_or_none()
    if obj is None:
        obj = model(name=name, **extra)
        db.add(obj)
        await db.flush()
    return obj


async def seed() -> None:
    data = json.loads(SEED_FILE.read_text())

    async with AsyncSessionLocal() as db:
        business_units = {}
        for name in data["business_units"]:
            business_units[name] = await _get_or_create(db, BusinessUnit, name=name)

        branches = {}
        for entry in data["branches"]:
            bu = business_units[entry["business_unit"]]
            branches[entry["name"]] = await _get_or_create(
                db, Branch, name=entry["name"], business_unit_id=bu.id
            )

        departments = {}
        for name in data["departments"]:
            departments[name] = await _get_or_create(db, Department, name=name)

        created, skipped = 0, 0
        for u in data["users"]:
            existing = await db.execute(
                select(User).where(
                    User.full_name == u["full_name"],
                    User.branch_id == (branches[u["branch"]].id if u.get("branch") else None),
                )
            )
            if existing.scalar_one_or_none() is not None:
                skipped += 1
                continue

            user = User(
                full_name=u["full_name"],
                email=u.get("email"),
                phone_number=u.get("phone"),
                job_title=u.get("job_title"),
                role=Role(u.get("role", "member")),
                is_active=u.get("is_active", True),
                department_id=departments[u["department"]].id if u.get("department") else None,
                branch_id=branches[u["branch"]].id if u.get("branch") else None,
                password_hash=None,
            )
            db.add(user)
            created += 1

        await db.commit()
        print(f"Seed complete: {created} users created, {skipped} already present (skipped).")


if __name__ == "__main__":
    asyncio.run(seed())
