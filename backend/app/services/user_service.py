"""
User lookups shared by the auth context (app/main.py), login/refresh
mutations, and any resolver that needs to map a User row onto the
GraphQL type (which requires `department` to already be eager-loaded —
see USER_EAGER_LOAD).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User

USER_EAGER_LOAD = (selectinload(User.department),)


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).options(*USER_EAGER_LOAD).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).options(*USER_EAGER_LOAD).where(User.email == email))
    return result.scalar_one_or_none()


async def list_users(db: AsyncSession, *, department_id: uuid.UUID | None = None) -> list[User]:
    query = select(User).options(*USER_EAGER_LOAD).order_by(User.full_name)
    if department_id is not None:
        query = query.where(User.department_id == department_id)
    result = await db.execute(query)
    return list(result.scalars().all())
