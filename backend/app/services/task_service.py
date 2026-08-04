"""
Business logic for tasks, kept out of GraphQL resolvers so it's reusable
from REST endpoints, Celery jobs, or tests without going through GraphQL.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_log import NotificationTrigger  # noqa: F401 (referenced in TODO docstrings below)
from app.models.task import Task, ticket_number_seq
from app.services.notifications import enqueue_if_needed  # noqa: F401 (referenced in TODO docstrings below)


async def next_ticket_no(db: AsyncSession) -> str:
    """
    Generates the next human-readable ticket number, e.g. "TCK-3021",
    matching the format already shown throughout the UI prototypes.
    """
    result = await db.execute(select(func.nextval(ticket_number_seq.name)))
    n = result.scalar_one()
    return f"TCK-{n:04d}"


async def create_task(db: AsyncSession, *, actor, input) -> Task:
    """
    TODO: implement.
      1. ticket_no = await next_ticket_no(db)
      2. task = Task(ticket_no=ticket_no, reporter_id=actor.id, **input mapped to model fields)
      3. db.add(task); await db.commit(); await db.refresh(task)
      4. enqueue_if_needed(task, NotificationTrigger.TASK_CREATED) — fires
         SMS/email to the assignee (+ department managers if URGENT) when
         `input.priority` is HIGH/URGENT. See app/services/notifications.py.
      5. return task
    """
    raise NotImplementedError


async def update_task(db: AsyncSession, *, actor, task: Task, input) -> Task:
    """
    TODO: implement (apply `input` fields onto `task`, persist), then:

      previously_notifiable = task.priority in (TaskPriority.HIGH, TaskPriority.URGENT)
      # ... apply changes ...
      now_notifiable = task.priority in (TaskPriority.HIGH, TaskPriority.URGENT)

      if input.assignee_id is not None:
          enqueue_if_needed(task, NotificationTrigger.TASK_ASSIGNED)
      elif not previously_notifiable and now_notifiable:
          enqueue_if_needed(task, NotificationTrigger.PRIORITY_ESCALATED)

    i.e. only notify on assignment or on an *escalation into* high/urgent —
    not on every unrelated edit to an already-high-priority ticket, to
    avoid notification fatigue.
    """
    raise NotImplementedError
