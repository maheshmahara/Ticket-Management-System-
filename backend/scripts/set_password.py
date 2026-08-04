"""
Sets (or resets) a user's password by email — the missing piece between
"seeded into the org chart" (scripts/seed_staff.py leaves password_hash
NULL on purpose) and "can actually log in".

There's no self-serve "sign up" flow yet (this is a single-org, admin-
provisioned system per the RBAC design), so this is the current way to
give someone login access: an admin runs this once per person.

Usage:
    python scripts/set_password.py <email> <password>

Example:
    docker-compose exec api python scripts/set_password.py mbdekkaido@gmail.com "correct-horse-battery-staple"

Requires DATABASE_URL / JWT_SECRET_KEY to be set and the DB schema to
already be migrated (alembic upgrade head) — same as seed_staff.py.
"""

import asyncio
import sys
from pathlib import Path

# See scripts/seed_staff.py for why this is necessary: running a script
# by path only puts *that script's own directory* on sys.path, not
# backend/ (which contains the `app` package).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.user import User  # noqa: E402


async def set_password(email: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            print(f"No user found with email {email!r}.")
            print("Emails on file come from the source spreadsheet — many seeded")
            print("staff (mostly restaurant roles) have none. Check backend/seed_data/staff.json.")
            return

        user.password_hash = hash_password(password)
        await db.commit()
        print(f"Password set for {user.full_name} <{email}> (role={user.role.value}). They can now log in.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(1)

    asyncio.run(set_password(sys.argv[1], sys.argv[2]))
