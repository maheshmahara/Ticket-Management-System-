"""
Business logic for the org structure (Departments, BusinessUnits, Branches)
and admin-only user management. Kept out of GraphQL resolvers for the same
reason as task_service.py — resolvers stay thin (authenticate/authorize,
delegate, map to GraphQL types).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.graphql.errors import app_error
from app.models.branch import Branch
from app.models.business_unit import BusinessUnit
from app.models.department import Department
from app.models.user import Role, User
from app.services.user_service import USER_EAGER_LOAD, get_user_by_id

BRANCH_EAGER_LOAD = (selectinload(Branch.business_unit),)
BUSINESS_UNIT_EAGER_LOAD = (selectinload(BusinessUnit.branches),)


# --- Departments ---


async def list_departments(db: AsyncSession) -> list[Department]:
    result = await db.execute(select(Department).order_by(Department.name))
    return list(result.scalars().all())


async def create_department(db: AsyncSession, *, name: str) -> Department:
    department = Department(name=name.strip())
    db.add(department)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise app_error("VALIDATION_ERROR", f'A department named "{name}" already exists.')
    await db.refresh(department)
    return department


# --- Business Units & Branches ---


async def list_business_units(db: AsyncSession) -> list[BusinessUnit]:
    result = await db.execute(
        select(BusinessUnit).options(*BUSINESS_UNIT_EAGER_LOAD).order_by(BusinessUnit.name)
    )
    return list(result.scalars().all())


async def create_business_unit(db: AsyncSession, *, name: str) -> BusinessUnit:
    business_unit = BusinessUnit(name=name.strip())
    db.add(business_unit)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise app_error("VALIDATION_ERROR", f'A business unit named "{name}" already exists.')

    # Re-select with `.branches` eager-loaded rather than `db.refresh()` +
    # touching the relationship directly — assigning/reading an unloaded
    # collection relationship on an AsyncSession-backed object triggers a
    # synchronous lazy-load under the hood, which raises MissingGreenlet
    # ("greenlet_spawn has not been called") outside of SQLAlchemy's async
    # greenlet context. Found by actually executing this mutation against
    # a real (in-memory) async session, not caught by any import/compile
    # check — same class of bug as the eager-load notes elsewhere in this
    # codebase (see TASK_EAGER_LOAD's docstring in task_service.py).
    result = await db.execute(
        select(BusinessUnit).options(*BUSINESS_UNIT_EAGER_LOAD).where(BusinessUnit.id == business_unit.id)
    )
    return result.scalar_one()


async def create_branch(db: AsyncSession, *, name: str, business_unit_id: uuid.UUID, is_active: bool) -> Branch:
    business_unit = await db.get(BusinessUnit, business_unit_id)
    if business_unit is None:
        raise app_error("NOT_FOUND", "Business unit not found.")

    branch = Branch(name=name.strip(), business_unit_id=business_unit_id, is_active=is_active)
    db.add(branch)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise app_error("VALIDATION_ERROR", f'A branch named "{name}" already exists.')

    result = await db.execute(select(Branch).options(*BRANCH_EAGER_LOAD).where(Branch.id == branch.id))
    return result.scalar_one()


async def update_branch(db: AsyncSession, *, branch_id: uuid.UUID, name: str | None, is_active: bool | None) -> Branch:
    result = await db.execute(select(Branch).options(*BRANCH_EAGER_LOAD).where(Branch.id == branch_id))
    branch = result.scalar_one_or_none()
    if branch is None:
        raise app_error("NOT_FOUND", "Branch not found.")

    if name is not None:
        branch.name = name.strip()
    if is_active is not None:
        branch.is_active = is_active

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise app_error("VALIDATION_ERROR", f'A branch named "{name}" already exists.')

    result = await db.execute(select(Branch).options(*BRANCH_EAGER_LOAD).where(Branch.id == branch_id))
    return result.scalar_one()


# --- Admin user management ---
# (Separate from the self-service bits in user_service.py / the
# update_notification_preferences mutation — everything here is gated with
# permission_classes=[IsAdmin] at the resolver level in mutations.py.)


async def create_user(db: AsyncSession, *, input) -> User:
    user = User(
        full_name=input.full_name.strip(),
        email=(input.email or "").strip() or None,
        password_hash=hash_password(input.password),
        role=Role(input.role.value),
        department_id=uuid.UUID(str(input.department_id)) if input.department_id else None,
        branch_id=uuid.UUID(str(input.branch_id)) if input.branch_id else None,
        job_title=input.job_title,
        phone_number=input.phone_number,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise app_error("VALIDATION_ERROR", f'A user with email "{input.email}" already exists.')

    return await get_user_by_id(db, user.id)


async def update_user(db: AsyncSession, *, user_id: uuid.UUID, input) -> User:
    result = await db.execute(select(User).options(*USER_EAGER_LOAD).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise app_error("NOT_FOUND", "User not found.")

    if input.full_name is not None:
        user.full_name = input.full_name.strip()
    if input.role is not None:
        user.role = Role(input.role.value)
    if input.department_id is not None:
        user.department_id = uuid.UUID(str(input.department_id))
    if input.branch_id is not None:
        user.branch_id = uuid.UUID(str(input.branch_id))
    if input.job_title is not None:
        user.job_title = input.job_title
    if input.phone_number is not None:
        user.phone_number = input.phone_number
    if input.is_active is not None:
        user.is_active = input.is_active
    if input.notify_email is not None:
        user.notify_email = input.notify_email
    if input.notify_sms is not None:
        user.notify_sms = input.notify_sms

    await db.commit()
    return await get_user_by_id(db, user_id)


async def reset_user_password(db: AsyncSession, *, user_id: uuid.UUID, new_password: str) -> User:
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise app_error("NOT_FOUND", "User not found.")

    user.password_hash = hash_password(new_password)
    await db.commit()
    return await get_user_by_id(db, user_id)
