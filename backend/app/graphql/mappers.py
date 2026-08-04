"""
Maps SQLAlchemy ORM rows onto the Strawberry GraphQL types in
app/graphql/types.py. Kept separate from both so resolvers stay thin and
the mapping logic (which fields, which nested relations) lives in one
place.

Every ORM object passed in here must already have its relationships
eager-loaded (selectinload) by the caller — see the *_EAGER_LOAD tuples
in app/services/*.py. Accessing an unloaded relationship on an
AsyncSession-backed object raises MissingGreenlet, not a clean error, so
this module deliberately does not lazy-load anything itself.
"""

import strawberry

from app.graphql import types as gql
from app.models.comment import Comment as CommentModel
from app.models.department import Department as DepartmentModel
from app.models.task import Task as TaskModel
from app.models.user import User as UserModel


def to_department(department: DepartmentModel) -> gql.Department:
    return gql.Department(id=strawberry.ID(str(department.id)), name=department.name)


def to_user(user: UserModel) -> gql.User:
    return gql.User(
        id=strawberry.ID(str(user.id)),
        email=user.email,
        full_name=user.full_name,
        role=gql.Role(user.role.value),
        department=to_department(user.department) if user.department else None,
        avatar_color=user.avatar_color,
        initials=user.initials,
        is_active=user.is_active,
        phone_number=user.phone_number,
        notify_email=user.notify_email,
        notify_sms=user.notify_sms,
    )


def to_comment(comment: CommentModel) -> gql.Comment:
    return gql.Comment(
        id=strawberry.ID(str(comment.id)),
        body=comment.body,
        author=to_user(comment.author),
        created_at=comment.created_at,
    )


def to_task(task: TaskModel) -> gql.Task:
    return gql.Task(
        id=strawberry.ID(str(task.id)),
        ticket_no=task.ticket_no,
        title=task.title,
        description=task.description,
        status=gql.TaskStatus(task.status.value),
        priority=gql.TaskPriority(task.priority.value),
        department=to_department(task.department),
        assignee=to_user(task.assignee) if task.assignee else None,
        reporter=to_user(task.reporter),
        due_at=task.due_at,
        is_overdue=task.is_overdue,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        comments=[to_comment(c) for c in task.comments],
    )
