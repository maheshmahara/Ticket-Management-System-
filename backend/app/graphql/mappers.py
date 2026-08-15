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
from app.models.branch import Branch as BranchModel
from app.models.business_unit import BusinessUnit as BusinessUnitModel
from app.models.comment import Comment as CommentModel
from app.models.department import Department as DepartmentModel
from app.models.task import Task as TaskModel
from app.models.user import User as UserModel


def to_department(department: DepartmentModel) -> gql.Department:
    return gql.Department(id=strawberry.ID(str(department.id)), name=department.name)


def to_business_unit_ref(business_unit: BusinessUnitModel) -> gql.BusinessUnitRef:
    return gql.BusinessUnitRef(id=strawberry.ID(str(business_unit.id)), name=business_unit.name)


def to_branch(branch: BranchModel) -> gql.Branch:
    """`branch.business_unit` must already be eager-loaded by the caller —
    see BRANCH_EAGER_LOAD in app/services/org_service.py."""
    return gql.Branch(
        id=strawberry.ID(str(branch.id)),
        name=branch.name,
        is_active=branch.is_active,
        business_unit=to_business_unit_ref(branch.business_unit),
    )


def to_business_unit(business_unit: BusinessUnitModel) -> gql.BusinessUnit:
    """`business_unit.branches` must already be eager-loaded by the caller.
    Each branch's own `.business_unit` is *not* re-fetched here — it's set
    directly from `business_unit` itself, since that's the same row and
    re-deriving it via branch.business_unit would need a second
    eager-loaded hop for no reason."""
    ref = to_business_unit_ref(business_unit)
    return gql.BusinessUnit(
        id=ref.id,
        name=ref.name,
        branches=[
            gql.Branch(id=strawberry.ID(str(b.id)), name=b.name, is_active=b.is_active, business_unit=ref)
            for b in business_unit.branches
        ],
    )


def to_user(user: UserModel) -> gql.User:
    return gql.User(
        id=strawberry.ID(str(user.id)),
        email=user.email,
        full_name=user.full_name,
        role=gql.Role(user.role.value),
        department=to_department(user.department) if user.department else None,
        job_title=user.job_title,
        branch=to_branch(user.branch) if user.branch else None,
        avatar_color=user.avatar_color,
        initials=user.initials,
        is_active=user.is_active,
        phone_number=user.phone_number,
        notify_email=user.notify_email,
        notify_sms=user.notify_sms,
        photo_base64=user.photo_base64,
        profile_completed_at=user.profile_completed_at,
        requested_role=gql.Role(user.requested_role.value) if user.requested_role else None,
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
        duration_minutes=task.duration_minutes,
        is_overdue=task.is_overdue,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        comments=[to_comment(c) for c in task.comments],
    )
