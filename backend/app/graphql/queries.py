"""
GraphQL query resolvers. Resolvers pull the DB session and current user off
`info.context` (wired in app/main.py's Strawberry context_getter).
"""

import base64
import uuid
from datetime import datetime
from typing import Optional

import strawberry
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from strawberry.types import Info

from app.graphql.errors import app_error
from app.graphql.mappers import to_business_unit, to_department, to_notification, to_task, to_user
from app.graphql.permissions import IsAdmin, IsAuthenticated, IsManagerOrAdmin, can_view_task
from app.graphql.types import (
    BusinessUnit,
    DashboardStats,
    Department,
    DepartmentKpi,
    KpiReport,
    Notification,
    PageInfo,
    PageInput,
    ResolverLeaderboardEntry,
    Task,
    TaskConnection,
    TaskEdge,
    TaskFilterInput,
    TaskSortInput,
    User,
    UserWorkload,
)
from app.models.department import Department as DepartmentModel
from app.models.notification_log import NotificationLog as NotificationLogModel
from app.models.task import Task as TaskModel
from app.models.task import TaskPriority as TaskPriorityModel
from app.models.task import TaskStatus
from app.models.user import Role
from app.models.user import User as UserModel
from app.services import analytics_service, org_service
from app.services.task_service import TASK_EAGER_LOAD
from app.services.user_service import USER_EAGER_LOAD, list_users


def _encode_cursor(offset: int) -> str:
    return base64.b64encode(f"offset:{offset}".encode()).decode()


def _decode_cursor(cursor: str) -> int:
    return int(base64.b64decode(cursor.encode()).decode().split(":")[1])


_SORT_COLUMNS = {
    "createdAt": TaskModel.created_at,
    "dueAt": TaskModel.due_at,
    "priority": TaskModel.priority,
}


@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAuthenticated])
    async def me(self, info: Info) -> Optional[User]:
        user = info.context.user
        return to_user(user) if user is not None else None

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def dashboard_stats(
        self, info: Info, department_id: Optional[strawberry.ID] = None
    ) -> DashboardStats:
        db = info.context.db
        user = info.context.user

        # RBAC scoping must match the `tasks` query below: non-admins see
        # their own department's tasks there *plus* anything assigned to
        # or reported by them regardless of department (a normal
        # cross-department handoff). Counting only by department here —
        # or org-wide — produced dashboard tiles that disagreed with "My
        # Tasks": e.g. dashboard said "2 Pending" while the filtered list
        # showed none, because those pending tasks weren't in the user's
        # department and (at the time) the list didn't check
        # assignee/reporter either. Admins may still pass an explicit
        # department_id to drill into any single department; non-admins
        # always get their own-department-or-own-task scope regardless
        # of the argument, since they can't see other departments'
        # unrelated tasks anyway.
        scope_clause = None
        if user.role != Role.ADMIN:
            scope_clause = or_(
                TaskModel.department_id == user.department_id,
                TaskModel.assignee_id == user.id,
                TaskModel.reporter_id == user.id,
            )
        elif department_id is not None:
            scope_clause = TaskModel.department_id == uuid.UUID(str(department_id))

        base_query = select(TaskModel.status, func.count()).group_by(TaskModel.status)
        if scope_clause is not None:
            base_query = base_query.where(scope_clause)

        result = await db.execute(base_query)
        counts = {status: count for status, count in result.all()}

        # "Overdue" is computed (due_at < now, not done), not a stored
        # status — see docs/BACKEND_ARCHITECTURE.md open questions.
        overdue_query = select(func.count()).select_from(TaskModel).where(
            TaskModel.due_at.is_not(None),
            TaskModel.due_at < func.now(),
            TaskModel.status != TaskStatus.DONE,
        )
        if scope_clause is not None:
            overdue_query = overdue_query.where(scope_clause)
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
        return [to_department(d) for d in result.scalars().all()]

    @strawberry.field(permission_classes=[IsAdmin])
    async def business_units(self, info: Info) -> list[BusinessUnit]:
        db = info.context.db
        rows = await org_service.list_business_units(db)
        return [to_business_unit(bu) for bu in rows]

    @strawberry.field(permission_classes=[IsAdmin])
    async def pending_role_requests(self, info: Info) -> list[User]:
        db = info.context.db
        result = await db.execute(
            select(UserModel)
            .options(*USER_EAGER_LOAD)
            .where(UserModel.requested_role.is_not(None))
            .order_by(UserModel.full_name)
        )
        return [to_user(u) for u in result.scalars().all()]

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def my_notifications(self, info: Info) -> list[Notification]:
        """Powers the topbar bell. NotificationLog has one row *per
        channel* (a user with both email+SMS enabled gets two rows for
        the same event) — overfetch a bit past the target count and
        dedupe by (task_id, trigger) in Python, keeping the most recent
        row per pair, since that's simpler than a window-function query
        for a feed this small. See Notification's docstring for why
        there's no separate "unread" field — the client compares
        created_at against User.notifications_last_seen_at instead."""
        db = info.context.db
        user = info.context.user

        result = await db.execute(
            select(NotificationLogModel)
            .options(selectinload(NotificationLogModel.task))
            .where(NotificationLogModel.recipient_id == user.id)
            .order_by(NotificationLogModel.created_at.desc())
            .limit(60)
        )
        rows = result.scalars().all()

        seen_keys = set()
        deduped = []
        for row in rows:
            key = (row.task_id, row.trigger)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(row)
            if len(deduped) >= 20:
                break

        return [to_notification(row) for row in deduped]

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def users(self, info: Info, department_id: Optional[strawberry.ID] = None) -> list[User]:
        db = info.context.db
        dept_uuid = uuid.UUID(str(department_id)) if department_id is not None else None
        rows = await list_users(db, department_id=dept_uuid)
        return [to_user(u) for u in rows]

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def user_workloads(
        self, info: Info, department_id: Optional[strawberry.ID] = None
    ) -> list[UserWorkload]:
        """Powers the Kanban board's inline assignee picker. `department_id`
        only narrows which *users* are returned as candidates (e.g. only
        show a department's own staff in that department's board) — the
        open-ticket count attached to each one is always platform-wide, not
        scoped to that department, so "is this person already busy?" means
        the same thing regardless of which board you're looking at."""
        db = info.context.db
        dept_uuid = uuid.UUID(str(department_id)) if department_id is not None else None
        candidates = await list_users(db, department_id=dept_uuid)

        counts_query = (
            select(TaskModel.assignee_id, func.count())
            .where(TaskModel.assignee_id.is_not(None), TaskModel.status != TaskStatus.DONE)
            .group_by(TaskModel.assignee_id)
        )
        counts = dict((await db.execute(counts_query)).all())

        return [
            UserWorkload(user=to_user(u), open_task_count=counts.get(u.id, 0))
            for u in candidates
        ]

    @strawberry.field(permission_classes=[IsManagerOrAdmin])
    async def kpi_report(self, info: Info, start: datetime, end: datetime) -> KpiReport:
        """Admins get every department; Managers get a strict match on
        their own department_id only — deliberately NOT the
        OR-with-own-tasks scope dashboard_stats/tasks use above, since a
        KPI report about "my department's performance" shouldn't also
        pull in one unrelated cross-department ticket a manager happens
        to be personally assigned. Members can't reach this resolver at
        all (field-level IsManagerOrAdmin gate)."""
        if start >= end:
            raise app_error("VALIDATION_ERROR", "Start date must be before end date.")

        db = info.context.db
        user = info.context.user

        department_id = None
        if user.role == Role.MANAGER:
            if user.department_id is None:
                raise app_error("VALIDATION_ERROR", "Your account has no department assigned.")
            department_id = user.department_id

        dept_rows = await analytics_service.department_resolution_stats(
            db, department_id=department_id, start=start, end=end
        )
        fastest, most_closed = await analytics_service.resolver_leaderboard(
            db, department_id=department_id, start=start, end=end
        )

        def _entry(row) -> ResolverLeaderboardEntry:
            u, avg_seconds, closed_count = row
            return ResolverLeaderboardEntry(
                user_id=strawberry.ID(str(u.id)),
                full_name=u.full_name,
                avatar_color=u.avatar_color,
                initials=u.initials,
                avg_resolution_seconds=float(avg_seconds),
                closed_count=closed_count,
            )

        return KpiReport(
            departments=[
                DepartmentKpi(
                    department_id=strawberry.ID(str(dept_id)),
                    department_name=name,
                    avg_resolution_seconds=float(avg_seconds),
                    completed_count=count,
                )
                for dept_id, name, avg_seconds, count in dept_rows
            ],
            fastest_resolvers=[_entry(r) for r in fastest],
            most_tickets_closed=[_entry(r) for r in most_closed],
        )

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def task(self, info: Info, id: strawberry.ID) -> Optional[Task]:
        db = info.context.db
        result = await db.execute(select(TaskModel).options(*TASK_EAGER_LOAD).where(TaskModel.id == uuid.UUID(str(id))))
        task_row = result.scalar_one_or_none()
        if task_row is None:
            return None
        if not can_view_task(info.context.user, task_row):
            raise app_error("FORBIDDEN", "You don't have access to this task.")
        return to_task(task_row)

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def tasks(
        self,
        info: Info,
        filter: Optional[TaskFilterInput] = None,
        sort: Optional[TaskSortInput] = None,
        page: Optional[PageInput] = None,
    ) -> TaskConnection:
        db = info.context.db
        user = info.context.user

        query = select(TaskModel)

        # RBAC scoping: only Admins see across departments (matches the
        # "View all departments' tasks" row in the permission matrix) —
        # but non-admins also see any task assigned to or reported by
        # them regardless of department, mirroring can_view_task /
        # can_edit_task's own-task carve-out. Without the OR, a task
        # filed under a different department than its assignee (a
        # normal cross-department handoff) was completely invisible to
        # the person actually assigned to do it, even though they could
        # edit it if they somehow got the link.
        if user.role != Role.ADMIN:
            query = query.where(
                or_(
                    TaskModel.department_id == user.department_id,
                    TaskModel.assignee_id == user.id,
                    TaskModel.reporter_id == user.id,
                )
            )

        if filter is not None:
            if filter.status is not None:
                query = query.where(TaskModel.status == TaskStatus(filter.status.value))
            if filter.priority is not None:
                query = query.where(TaskModel.priority == TaskPriorityModel(filter.priority.value))
            if filter.department_id is not None:
                query = query.where(TaskModel.department_id == uuid.UUID(str(filter.department_id)))
            if filter.exclude_done:
                query = query.where(TaskModel.status != TaskStatus.DONE)
            if filter.assignee_id is not None:
                query = query.where(TaskModel.assignee_id == uuid.UUID(str(filter.assignee_id)))
            if filter.search:
                query = query.where(TaskModel.title.ilike(f"%{filter.search}%"))

        count_query = select(func.count()).select_from(query.with_only_columns(TaskModel.id).subquery())
        total_count = (await db.execute(count_query)).scalar_one()

        sort_column = _SORT_COLUMNS.get(sort.field, TaskModel.created_at) if sort else TaskModel.created_at
        query = query.order_by(sort_column.desc() if sort and sort.direction.upper() == "DESC" else sort_column.asc())

        first = page.first if page and page.first else 25
        offset = _decode_cursor(page.after) + 1 if page and page.after else 0

        result = await db.execute(query.options(*TASK_EAGER_LOAD).offset(offset).limit(first))
        rows = list(result.scalars().all())

        edges = [TaskEdge(cursor=_encode_cursor(offset + i), node=to_task(t)) for i, t in enumerate(rows)]
        has_next_page = offset + len(rows) < total_count

        return TaskConnection(
            edges=edges,
            page_info=PageInfo(has_next_page=has_next_page, end_cursor=edges[-1].cursor if edges else None),
            total_count=total_count,
        )
