"""
GraphQL query resolvers. Resolvers pull the DB session and current user off
`info.context` (wired in app/main.py's Strawberry context_getter).

These are written against the real ORM models in app/models/ so the shape
is correct, but a few spots (search, cursor pagination decode) are left as
TODOs — see docs/BACKEND_ARCHITECTURE.md for the intended design.
"""

import base64
from typing import Optional

import strawberry
from sqlalchemy import func, select
from strawberry.types import Info

from app.graphql.permissions import IsAuthenticated
from app.graphql.types import (
    DashboardStats,
    Department,
    PageInfo,  # noqa: F401 (used by resolvers once tasks() is implemented)
    PageInput,
    Task,
    TaskConnection,
    TaskEdge,  # noqa: F401
    TaskFilterInput,
    TaskSortInput,
    User,
)
from app.models.department import Department as DepartmentModel
from app.models.task import Task as TaskModel
from app.models.task import TaskStatus


def _encode_cursor(offset: int) -> str:
    return base64.b64encode(f"offset:{offset}".encode()).decode()


def _decode_cursor(cursor: str) -> int:
    return int(base64.b64decode(cursor.encode()).decode().split(":")[1])


@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAuthenticated])
    async def me(self, info: Info) -> Optional[User]:
        # TODO: map info.context.user (ORM UserModel) -> User GraphQL type
        raise NotImplementedError("Wire up context.user -> User type mapping")

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def dashboard_stats(
        self, info: Info, department_id: Optional[strawberry.ID] = None
    ) -> DashboardStats:
        db = info.context.db
        base_query = select(TaskModel.status, func.count()).group_by(TaskModel.status)
        if department_id is not None:
            base_query = base_query.where(TaskModel.department_id == department_id)

        result = await db.execute(base_query)
        counts = {status: count for status, count in result.all()}

        # "Overdue" is computed (due_at < now, not done), not a stored
        # status — see docs/BACKEND_ARCHITECTURE.md open questions.
        overdue_query = select(func.count()).select_from(TaskModel).where(
            TaskModel.due_at.is_not(None),
            TaskModel.due_at < func.now(),
            TaskModel.status != TaskStatus.DONE,
        )
        if department_id is not None:
            overdue_query = overdue_query.where(TaskModel.department_id == department_id)
        overdue_count = (await db.execute(overdue_query)).scalar_one()

        return DashboardStats(
            pending=counts.get(TaskStatus.PENDING, 0),
            in_progress=counts.get(TaskStatus.IN_PROGRESS, 0),
            overdue=overdue_count,
            completed=counts.get(TaskStatus.DONE, 0),
        )

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def departments(self, info: Info) -> list[Department]:
        db = info.context.db
        result = await db.execute(select(DepartmentModel).order_by(DepartmentModel.name))
        return [Department(id=strawberry.ID(str(d.id)), name=d.name) for d in result.scalars().all()]

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def users(self, info: Info, department_id: Optional[strawberry.ID] = None) -> list[User]:
        # TODO: query UserModel (optionally filtered by department_id) and
        # map to the User GraphQL type, same pattern as `departments` above.
        raise NotImplementedError

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def task(self, info: Info, id: strawberry.ID) -> Optional[Task]:
        # TODO: load TaskModel by id (with department/assignee/reporter/comments
        # eagerly loaded), enforce RBAC visibility, map to Task GraphQL type.
        raise NotImplementedError

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def tasks(
        self,
        info: Info,
        filter: Optional[TaskFilterInput] = None,
        sort: Optional[TaskSortInput] = None,
        page: Optional[PageInput] = None,
    ) -> TaskConnection:
        # TODO: build the filtered/sorted query from `filter`/`sort`, apply
        # RBAC scoping (Member sees only their own tasks, Manager only their
        # department, Admin sees all — see permission matrix in the design
        # doc), then paginate using _encode_cursor/_decode_cursor and map
        # rows to Task/TaskEdge. Left unimplemented in this scaffold.
        raise NotImplementedError
