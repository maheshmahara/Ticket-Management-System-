"""
KPI/reporting aggregations, kept out of the GraphQL resolver like every
other business-logic module in app/services/. This is the first module in
this codebase to do multi-dimension duration/leaderboard aggregation
(dashboard_stats in queries.py is the only precedent, and it's a single
group_by(status) count — no func.avg, no duration math), so there's no
existing pattern beyond that to match against.

Every function here filters on `completed_at` falling inside [start, end)
— not `created_at` — since both the department breakdown and the two
leaderboards are meant to describe "activity completed in this period",
not a mix of "created in X" and "closed in X" semantics across the same
report.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department as DepartmentModel
from app.models.task import Task as TaskModel
from app.models.task import TaskStatus
from app.models.user import User as UserModel


def _duration_seconds():
    return func.extract("epoch", TaskModel.completed_at - TaskModel.created_at)


async def department_resolution_stats(
    db: AsyncSession, *, department_id: uuid.UUID | None, start: datetime, end: datetime
):
    """One query: department id/name, average resolution time in seconds,
    and count of tickets closed in [start, end). Department name comes
    from the join itself — no separate per-department lookup."""
    query = (
        select(
            DepartmentModel.id,
            DepartmentModel.name,
            func.avg(_duration_seconds()),
            func.count(TaskModel.id),
        )
        .join(TaskModel, TaskModel.department_id == DepartmentModel.id)
        .where(
            TaskModel.status == TaskStatus.DONE,
            TaskModel.completed_at.is_not(None),
            TaskModel.completed_at >= start,
            TaskModel.completed_at < end,
        )
        .group_by(DepartmentModel.id, DepartmentModel.name)
        .order_by(DepartmentModel.name)
    )
    if department_id is not None:
        query = query.where(DepartmentModel.id == department_id)
    return (await db.execute(query)).all()


async def resolver_leaderboard(
    db: AsyncSession,
    *,
    department_id: uuid.UUID | None,
    start: datetime,
    end: datetime,
    limit: int = 10,
):
    """One query — user row + average resolution time + closed count,
    joined on Task.assignee_id — sorted two different ways in Python to
    produce both leaderboards (fastest-average, most-closed) without
    querying twice. User identity comes from the join itself, same
    no-separate-lookup approach as the department stats above."""
    query = (
        select(UserModel, func.avg(_duration_seconds()), func.count(TaskModel.id))
        .join(TaskModel, TaskModel.assignee_id == UserModel.id)
        .where(
            TaskModel.status == TaskStatus.DONE,
            TaskModel.completed_at.is_not(None),
            TaskModel.completed_at >= start,
            TaskModel.completed_at < end,
        )
    )
    if department_id is not None:
        query = query.where(TaskModel.department_id == department_id)
    # UserModel.id is the primary key, so grouping by it alone (rather
    # than every selected UserModel column) is legal under Postgres'
    # functional-dependency rule for GROUP BY.
    query = query.group_by(UserModel.id)

    rows = (await db.execute(query)).all()
    fastest = sorted(rows, key=lambda r: r[1])[:limit]
    most_closed = sorted(rows, key=lambda r: r[2], reverse=True)[:limit]
    return fastest, most_closed
