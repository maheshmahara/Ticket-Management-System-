"""
SMS + Email notifications for high/urgent priority tickets.

Trigger points (wired into app/services/task_service.py — see the
`notify_if_high_priority` calls referenced there):
  - A new task is created with priority HIGH or URGENT.
  - An existing task is assigned to someone while at HIGH/URGENT priority.
  - A task's priority is escalated up to HIGH/URGENT.

Design notes (see docs/BACKEND_ARCHITECTURE.md "Notifications" section for
the full rationale):
  - Sending happens in a Celery task (`send_task_notifications`), never
    inline in a GraphQL resolver — a slow/down email or SMS provider must
    never make `createTask`/`updateTask` mutations hang or fail.
  - Each attempt is recorded in `notification_logs` *before* the send
    (status=QUEUED) and updated after (SENT/FAILED), so retries don't
    silently double-send and failures are auditable.
  - Respects each user's `notify_email` / `notify_sms` opt-in flags, and
    only fires for priorities listed in `settings.notify_priority_list`
    (defaults to "high,urgent").
  - The **assignee** is always notified (if assigned); the **department
    manager(s)** are additionally notified for URGENT tickets. (Open
    question: should the reporter also get a confirmation? Left out of v1
    to avoid over-notifying — revisit if requested.)
"""

import smtplib
import uuid
from email.mime.text import MIMEText

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.models.notification_log import (
    NotificationChannel,
    NotificationLog,
    NotificationStatus,
    NotificationTrigger,
)
from app.models.task import Task, TaskPriority
from app.models.user import Role, User

settings = get_settings()


def should_notify(priority: TaskPriority) -> bool:
    return settings.notifications_enabled and priority.value in settings.notify_priority_list


async def recipients_for_task(db: AsyncSession, task: Task, trigger: NotificationTrigger) -> list[User]:
    """
    Assignee always; department managers/admins too, but only for the
    highest-severity trigger (priority escalated to URGENT) to avoid
    notification fatigue on every high-priority ticket.
    """
    recipients: list[User] = []

    if task.assignee is not None:
        recipients.append(task.assignee)

    if task.priority == TaskPriority.URGENT:
        result = await db.execute(
            select(User).where(
                User.department_id == task.department_id,
                User.role.in_([Role.MANAGER, Role.ADMIN]),
                User.is_active.is_(True),
            )
        )
        recipients.extend(result.scalars().all())

    # De-dupe (a manager could also be the assignee)
    seen: set = set()
    unique: list[User] = []
    for user in recipients:
        if user.id not in seen:
            seen.add(user.id)
            unique.append(user)
    return unique


@celery_app.task(name="app.services.notifications.send_task_notifications", bind=True, max_retries=3)
def send_task_notifications(self, task_id: str, trigger: str) -> None:
    """
    Celery entrypoint. Synchronous wrapper around the async DB/send logic —
    Celery tasks are sync by default; see the TODO in
    app/core/celery_app.py if this needs to move to a fully async worker
    (e.g. via `asgiref.sync.async_to_sync` or an async-capable queue).
    """
    import asyncio

    asyncio.run(_send_task_notifications_async(task_id, NotificationTrigger(trigger)))


async def _send_task_notifications_async(task_id: str, trigger: NotificationTrigger) -> None:
    # Imported here (not at module top) to avoid a circular import: this
    # module is imported by app.core.celery_app at load time, and
    # app.core.database imports app.core.config, which is safe, but
    # keeping DB imports local to functions that actually need them keeps
    # this module importable even before the DB layer is fully wired.
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task)
            .options(selectinload(Task.department), selectinload(Task.assignee))
            .where(Task.id == uuid.UUID(task_id))
        )
        task = result.scalar_one_or_none()
        if task is None or not should_notify(task.priority):
            # Priority may have changed (or the task may have been
            # deleted) since this job was enqueued — re-check rather than
            # trusting the state at enqueue time.
            return

        recipients = await recipients_for_task(db, task, trigger)
        for user in recipients:
            if user.notify_email and user.email:
                await _send_and_log(db, task, user, NotificationChannel.EMAIL, trigger)
            if user.notify_sms and user.phone_number:
                await _send_and_log(db, task, user, NotificationChannel.SMS, trigger)


async def _send_and_log(
    db: AsyncSession, task: Task, user: User, channel: NotificationChannel, trigger: NotificationTrigger
) -> None:
    log = NotificationLog(
        task_id=task.id,
        recipient_id=user.id,
        channel=channel,
        trigger=trigger,
        status=NotificationStatus.QUEUED,
    )
    db.add(log)
    await db.commit()

    try:
        if channel == NotificationChannel.EMAIL:
            provider_id = _send_email(to=user.email, subject=_subject(task), body=_body(task, user))
        else:
            provider_id = _send_sms(to=user.phone_number, body=_sms_body(task))

        log.status = NotificationStatus.SENT
        log.provider_message_id = provider_id
    except Exception as exc:  # noqa: BLE001 — deliberately broad: log any provider failure
        log.status = NotificationStatus.FAILED
        log.error = str(exc)
    finally:
        await db.commit()


def _subject(task: Task) -> str:
    return f"[{task.priority.value.upper()}] {task.ticket_no} — {task.title}"


def _body(task: Task, user: User) -> str:
    return (
        f"Hi {user.full_name.split()[0]},\n\n"
        f"Ticket {task.ticket_no} ({task.priority.value} priority) needs your attention:\n\n"
        f"  {task.title}\n\n"
        f"Due: {task.due_at or 'No due date set'}\n\n"
        f"— HNBG Task Management System"
    )


def _sms_body(task: Task) -> str:
    # Keep SMS short — most carriers truncate around 160 chars per segment.
    return f"[HNBG] {task.priority.value.upper()} ticket {task.ticket_no}: {task.title[:80]}"


def _send_email(to: str, subject: str, body: str) -> str:
    """Returns a provider message id. Raises on failure."""
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = to

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(settings.smtp_from_email, [to], msg.as_string())

    return msg.get("Message-Id", "")


def _send_sms(to: str, body: str) -> str:
    """Returns the Twilio message SID. Raises on failure."""
    # Imported lazily so `twilio` isn't a hard dependency for anyone running
    # only email notifications / running tests without it installed.
    from twilio.rest import Client

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    message = client.messages.create(to=to, from_=settings.twilio_from_number, body=body)
    return message.sid


def enqueue_if_needed(task: Task, trigger: NotificationTrigger) -> None:
    """
    Call this from task_service.py after create/update/assign — fire-and-
    forget enqueue, never awaited inline in a resolver's critical path.
    """
    if should_notify(task.priority):
        send_task_notifications.delay(str(task.id), trigger.value)
