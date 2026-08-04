"""
RBAC enforcement for GraphQL resolvers.

Applied per-field via `@strawberry.field(permission_classes=[...])`, not
just at the HTTP layer, per the "Enforced via a GraphQL field/resolver-level
permission layer" note in docs/BACKEND_ARCHITECTURE.md.

See the permission matrix in that doc for the source of truth this maps to.
"""

import typing

from strawberry.permission import BasePermission
from strawberry.types import Info

from app.models.user import Role


class IsAuthenticated(BasePermission):
    message = "You must be logged in."

    def has_permission(self, source: typing.Any, info: Info, **kwargs) -> bool:
        return _current_user(info) is not None


class IsAdmin(BasePermission):
    message = "This action requires administrator privileges."

    def has_permission(self, source: typing.Any, info: Info, **kwargs) -> bool:
        user = _current_user(info)
        return user is not None and user.role == Role.ADMIN


class IsManagerOrAdmin(BasePermission):
    message = "This action requires manager or administrator privileges."

    def has_permission(self, source: typing.Any, info: Info, **kwargs) -> bool:
        user = _current_user(info)
        return user is not None and user.role in (Role.ADMIN, Role.MANAGER)


def _current_user(info: Info):
    """
    The authenticated user is expected to be attached to the GraphQL
    context by a FastAPI dependency that decodes the `Authorization:
    Bearer <token>` header before the request reaches Strawberry — see
    app/main.py's context_getter. `None` means unauthenticated.
    """
    return getattr(info.context, "user", None)


def can_edit_task(user, task) -> bool:
    """
    Object-level check used inside mutation resolvers (updateTask,
    deleteTask, assignTask) once a specific Task row has been loaded —
    can't be expressed as a plain field permission since it depends on
    the task's own department/reporter/assignee.
    """
    if user.role == Role.ADMIN:
        return True
    if user.role == Role.MANAGER:
        return user.department_id == task.department_id
    # MEMBER: only their own tasks (assigned to them or reported by them)
    return user.id in (task.assignee_id, task.reporter_id)
