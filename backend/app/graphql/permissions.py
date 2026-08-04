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
    # Without this, Strawberry's default on_unauthorized() raises a plain
    # GraphQLError with *no* `code` extension at all — meaning every
    # `err.code === "FORBIDDEN"` check on the frontend (api.js and every
    # page that calls it) silently never matched, so an expired/invalid
    # JWT never actually bounced the user back to login; it just showed
    # a raw "You must be logged in." error message instead. Found while
    # writing tests for the admin panel's IsAdmin-gated mutations, which
    # have the exact same gap.
    error_extensions = {"code": "FORBIDDEN"}

    def has_permission(self, source: typing.Any, info: Info, **kwargs) -> bool:
        return _current_user(info) is not None


class IsAdmin(BasePermission):
    message = "This action requires administrator privileges."
    error_extensions = {"code": "FORBIDDEN"}

    def has_permission(self, source: typing.Any, info: Info, **kwargs) -> bool:
        user = _current_user(info)
        return user is not None and user.role == Role.ADMIN


class IsManagerOrAdmin(BasePermission):
    message = "This action requires manager or administrator privileges."
    error_extensions = {"code": "FORBIDDEN"}

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


def can_view_task(user, task) -> bool:
    """
    Per the RBAC matrix: everyone can view tasks in their own department;
    only Admins can view tasks outside it. Additionally, resolving the
    open question in docs/BACKEND_ARCHITECTURE.md ("do Members need to
    see tasks outside their own department?"): yes, if it's assigned to
    or reported by them — otherwise `can_edit_task`'s existing
    "MEMBER: only their own tasks (assigned to them or reported by
    them)" carve-out below is unreachable in practice, since a Member
    can never load a cross-department task to begin with (this
    function blocks it, and the `tasks` list resolver never returns
    it). A task filed under a different department than the assignee
    (e.g. Marketing files a ticket and hands it to someone in Finance)
    is a normal cross-department handoff, not something that should be
    invisible to the person actually doing the work.
    """
    if user.role == Role.ADMIN:
        return True
    if user.department_id == task.department_id:
        return True
    return user.id in (task.assignee_id, task.reporter_id)


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
