"""
Business logic for tasks, kept out of GraphQL resolvers so it's reusable
from REST endpoints, Celery jobs, or tests without going through GraphQL.

Every function that returns a Task re-fetches it through `get_task()`
after committing, so the row it hands back always has its relationships
(department/assignee/reporter/comments) eager-loaded and ready for
app.graphql.mappers.to_task() — accessing an unloaded relationship on an
AsyncSession object raises MissingGreenlet, not a clean error.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.graphql.permissions import can_edit_task
from app.models.branch import Branch
from app.models.comment import Comment
from app.models.notification_log import NotificationTrigger
from app.models.task import Task, TaskPriority, TaskStatus, ticket_number_seq
from app.models.task_attachment import TaskAttachment
from app.models.user import User
from app.services.notifications import enqueue_assignment_notification, enqueue_if_needed
from app.services.user_service import USER_EAGER_LOAD  # noqa: F401 (re-exported for callers building User queries alongside tasks)

# Every User nested under a Task (assignee/reporter/comment author) needs the
# same relationships loaded as USER_EAGER_LOAD, since app/graphql/mappers.py's
# to_user() reads user.branch.business_unit unconditionally — added when the
# admin panel's User.branch field was introduced. Duplicated per-path rather
# than reused directly because SQLAlchemy's selectinload chains have to be
# built from the actual attribute path being traversed (Task.assignee, not
# bare User), so USER_EAGER_LOAD's tuple can't just be spliced in here.
_USER_NESTED_LOAD = (selectinload(User.department), selectinload(User.branch).selectinload(Branch.business_unit))

TASK_EAGER_LOAD = (
    selectinload(Task.department),
    selectinload(Task.branch).selectinload(Branch.business_unit),
    selectinload(Task.assignee).options(*_USER_NESTED_LOAD),
    selectinload(Task.reporter).options(*_USER_NESTED_LOAD),
    selectinload(Task.comments).selectinload(Comment.author).options(*_USER_NESTED_LOAD),
    selectinload(Task.attachments).selectinload(TaskAttachment.uploaded_by).options(*_USER_NESTED_LOAD),
)

# Priorities that make a task notification-worthy. should_notify() in
# notifications.py does the actual settings-aware gate before anything is
# sent — this just decides when it's worth calling enqueue_if_needed() at all.
NOTIFIABLE_PRIORITIES = (TaskPriority.HIGH, TaskPriority.URGENT)


async def next_ticket_no(db: AsyncSession) -> str:
    """
    Generates the next human-readable ticket number, e.g. "TCK-3021",
    matching the format already shown throughout the UI prototypes.
    """
    result = await db.execute(select(func.nextval(ticket_number_seq.name)))
    n = result.scalar_one()
    return f"TCK-{n:04d}"


async def get_task(db: AsyncSession, task_id: uuid.UUID) -> Task | None:
    result = await db.execute(select(Task).options(*TASK_EAGER_LOAD).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def create_task(db: AsyncSession, *, actor: User, input) -> Task:
    task = Task(
        ticket_no=await next_ticket_no(db),
        title=input.title,
        description=input.description,
        status=TaskStatus(input.status.value),
        priority=TaskPriority(input.priority.value),
        department_id=uuid.UUID(str(input.department_id)),
        branch_id=uuid.UUID(str(input.branch_id)) if input.branch_id else None,
        assignee_id=uuid.UUID(str(input.assignee_id)) if input.assignee_id else None,
        reporter_id=actor.id,
        due_at=input.due_at,
        start_date=input.start_date,
        duration_minutes=input.duration_minutes,
    )
    db.add(task)
    await db.commit()

    task = await get_task(db, task.id)

    if task.assignee_id is not None:
        # Instant, any-priority "you've been assigned this" notification —
        # see enqueue_assignment_notification's docstring. Covers choosing
        # an assignee directly in the Create Task form, not just later
        # reassignment.
        enqueue_assignment_notification(task)
        # Skip the separate TASK_CREATED alert for HIGH priority here — its
        # only recipient would be the assignee (recipients_for_task only
        # adds managers for URGENT), who's already covered by the line
        # above, so it'd be a pure duplicate email with a different
        # subject line. For URGENT, still send it: recipients_for_task
        # additionally reaches department managers, which the assignment
        # notification above deliberately does not.
        if task.priority == TaskPriority.URGENT:
            enqueue_if_needed(task, NotificationTrigger.TASK_CREATED)
    else:
        enqueue_if_needed(task, NotificationTrigger.TASK_CREATED)
    return task


async def update_task(db: AsyncSession, *, actor: User, task: Task, input) -> Task:
    """
    Applies `input` fields onto `task`, persists, and enqueues a
    notification only on the two cases that actually warrant an alert:
    the assignee changed (any priority — instant "you've been assigned
    this" notification, not gated by priority), or the priority was
    escalated *into* HIGH/URGENT with no assignee change (not on every
    edit of an already-high-priority ticket, to avoid notification
    fatigue).
    """
    previously_notifiable = task.priority in NOTIFIABLE_PRIORITIES
    assignee_changed = False

    if input.title is not None:
        task.title = input.title
    if input.description is not None:
        task.description = input.description
    if input.department_id is not None:
        task.department_id = uuid.UUID(str(input.department_id))
    if input.branch_id is not None:
        task.branch_id = uuid.UUID(str(input.branch_id))
    if input.priority is not None:
        task.priority = TaskPriority(input.priority.value)
    if input.status is not None:
        _apply_status(task, TaskStatus(input.status.value))
    if input.due_at is not None:
        task.due_at = input.due_at
    if input.start_date is not None:
        task.start_date = input.start_date
    if input.duration_minutes is not None:
        task.duration_minutes = input.duration_minutes
    if input.assignee_id is not None:
        new_assignee_id = uuid.UUID(str(input.assignee_id))
        assignee_changed = new_assignee_id != task.assignee_id
        task.assignee_id = new_assignee_id

    await db.commit()
    # AsyncSessionLocal is configured with expire_on_commit=False (see
    # app/core/database.py — avoids MissingGreenlet pitfalls elsewhere),
    # so `task`'s already-loaded relationship attributes (department,
    # branch, assignee, ...) are NOT automatically invalidated by the
    # commit above. Without expiring them first, get_task()'s fresh
    # SELECT below finds this same object already in the session's
    # identity map with those relationships "already loaded" and skips
    # re-querying them — the mutation would return the *old*
    # department/branch/assignee even though the FK column itself was
    # written correctly (confirmed via a separate query: the DB row is
    # always right, only this in-memory response was stale). Found
    # while adding branch_id, but affects every FK field here, not just
    # the new one.
    #
    # Naming the relationship attributes explicitly matters:
    # db.expire(task) with no attribute_names expires *every* attribute
    # including plain columns like `id` — and `task.id` right below is
    # a synchronous access, so an expired `id` tries to lazy-reload
    # outside the awaited context and raises MissingGreenlet. Only the
    # relationships actually need invalidating; the FK scalar columns
    # were already updated in-memory above and don't need refreshing.
    db.expire(task, ["department", "branch", "assignee", "reporter", "comments", "attachments"])
    task = await get_task(db, task.id)

    now_notifiable = task.priority in NOTIFIABLE_PRIORITIES
    if assignee_changed and task.assignee_id is not None:
        # Any priority — see enqueue_assignment_notification's docstring.
        enqueue_assignment_notification(task)
    elif not previously_notifiable and now_notifiable:
        enqueue_if_needed(task, NotificationTrigger.PRIORITY_ESCALATED)

    return task


def _apply_status(task: Task, new_status: TaskStatus) -> None:
    if new_status == TaskStatus.DONE and task.status != TaskStatus.DONE:
        task.completed_at = datetime.now(timezone.utc)
    elif new_status != TaskStatus.DONE:
        task.completed_at = None
    task.status = new_status


async def assign_task(db: AsyncSession, *, task: Task, assignee_id: uuid.UUID | None) -> Task:
    changed = assignee_id != task.assignee_id
    task.assignee_id = assignee_id
    await db.commit()
    # Same expire_on_commit=False staleness as update_task above — the
    # already-loaded `task.assignee` relationship isn't invalidated by
    # commit(), so without this the returned Task (and hence this
    # mutation's own response) would still show the *previous* assignee.
    # Confirmed live: reassigning A -> B -> None returned B, then A,
    # then B again — one call behind — before this fix.
    db.expire(task, ["assignee"])
    task = await get_task(db, task.id)
    if changed and task.assignee_id is not None:
        # Any priority — see enqueue_assignment_notification's docstring.
        enqueue_assignment_notification(task)
    return task


async def change_task_status(db: AsyncSession, *, task: Task, status: TaskStatus) -> Task:
    _apply_status(task, status)
    await db.commit()
    return await get_task(db, task.id)


async def bulk_update_tasks(
    db: AsyncSession,
    *,
    actor: User,
    task_ids: list[uuid.UUID],
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    assignee_id: uuid.UUID | None = None,
) -> tuple[list[tuple[uuid.UUID, str]], list[Task]]:
    """Partial-success bulk update: applies whatever fields were given to
    every task the actor can edit, skips (and reports) the rest rather
    than failing the whole batch. `can_edit_task` is genuinely reachable
    per-task divergence in a bulk selection — e.g. a Manager can *view*
    (but not edit) a cross-department task assigned to them.

    `assignee_id` here always means "reassign to this person" — there's
    no bulk-unassign requirement, so unlike single-task `update_task`
    there's no separate "clear assignee" signal to thread through.

    Same per-row-commit convention as every other write in this module —
    no new transaction machinery, no all-or-nothing rollback. Notification
    logic mirrors `update_task`'s exactly (assignee change -> instant
    notification any priority; else priority escalated into
    HIGH/URGENT -> PRIORITY_ESCALATED), just looped per task instead of
    applied to one.

    Returns (failures, updated_tasks) where failures is a list of
    (task_id, reason) — reason is "NOT_FOUND" or "FORBIDDEN".
    """
    failures: list[tuple[uuid.UUID, str]] = []
    updated: list[Task] = []

    for task_id in task_ids:
        task = await get_task(db, task_id)
        if task is None:
            failures.append((task_id, "NOT_FOUND"))
            continue
        if not can_edit_task(actor, task):
            failures.append((task_id, "FORBIDDEN"))
            continue
        # Mirrors assign_task's own rule — see the RBAC matrix in
        # docs/BACKEND_ARCHITECTURE.md.
        if assignee_id is not None and actor.role.value == "member" and assignee_id != actor.id:
            failures.append((task_id, "FORBIDDEN"))
            continue

        previously_notifiable = task.priority in NOTIFIABLE_PRIORITIES
        assignee_changed = False

        if status is not None:
            _apply_status(task, status)
        if priority is not None:
            task.priority = priority
        if assignee_id is not None:
            assignee_changed = assignee_id != task.assignee_id
            task.assignee_id = assignee_id

        await db.commit()
        task = await get_task(db, task.id)
        updated.append(task)

        now_notifiable = task.priority in NOTIFIABLE_PRIORITIES
        if assignee_changed and task.assignee_id is not None:
            enqueue_assignment_notification(task)
        elif not previously_notifiable and now_notifiable:
            enqueue_if_needed(task, NotificationTrigger.PRIORITY_ESCALATED)

    return failures, updated


async def delete_task(db: AsyncSession, *, task: Task) -> None:
    await db.delete(task)
    await db.commit()


async def add_comment(db: AsyncSession, *, actor: User, task: Task, body: str) -> Comment:
    comment = Comment(task_id=task.id, author_id=actor.id, body=body)
    db.add(comment)
    await db.commit()

    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.author).selectinload(User.department))
        .where(Comment.id == comment.id)
    )
    return result.scalar_one()
