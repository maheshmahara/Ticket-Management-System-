"""
SMS + Email notifications.

Two different gating rules apply depending on *why* a notification is
firing — this was a deliberate product decision (see CHANGELOG.md):

  - TASK_ASSIGNED (someone is assigned/reassigned a task, including at
    creation time): fires **instantly, for every priority** — assignment
    is the "main asset" notification of this system, so it isn't gated
    by `settings.notify_priority_list` at all. Only the global
    `NOTIFICATIONS_ENABLED` kill-switch and the recipient's own
    `notify_email`/`notify_sms` opt-in still apply.
  - TASK_CREATED / PRIORITY_ESCALATED: unchanged from the original
    design — only fire for priorities in `settings.notify_priority_list`
    (defaults to "high,urgent"), and additionally reach the department's
    managers/admins for URGENT tickets. These are "someone should look
    at this ticket" alerts, not "this is now your task" alerts.

Design notes (see docs/BACKEND_ARCHITECTURE.md "Notifications" section for
the full rationale):
  - Sending happens in a Celery task (`send_task_notifications`), never
    inline in a GraphQL resolver — a slow/down email or SMS provider must
    never make `createTask`/`updateTask` mutations hang or fail.
  - Each attempt is recorded in `notification_logs` *before* the send
    (status=QUEUED) and updated after (SENT/FAILED), so retries don't
    silently double-send and failures are auditable.
  - Respects each user's `notify_email` / `notify_sms` opt-in flags.
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
    from app.core.database import AsyncSessionLocal, engine

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Task)
                .options(selectinload(Task.department), selectinload(Task.assignee))
                .where(Task.id == uuid.UUID(task_id))
            )
            task = result.scalar_one_or_none()
            if task is None:
                return  # deleted since this job was enqueued

            if trigger == NotificationTrigger.TASK_ASSIGNED:
                # Assignment notifications are unconditional on priority (see
                # module docstring) — only the master kill-switch applies.
                if not settings.notifications_enabled:
                    return
            elif not should_notify(task.priority):
                # Priority may have changed since this job was enqueued —
                # re-check rather than trusting the state at enqueue time.
                return

            recipients = await recipients_for_task(db, task, trigger)
            for user in recipients:
                if user.notify_email and user.email:
                    await _send_and_log(db, task, user, NotificationChannel.EMAIL, trigger)
                if user.notify_sms and user.phone_number:
                    await _send_and_log(db, task, user, NotificationChannel.SMS, trigger)
    finally:
        # `engine` is a module-level singleton (see app/core/database.py),
        # but this function is invoked via `asyncio.run()` from a *sync*
        # Celery task (send_task_notifications), so every call gets a
        # brand-new event loop. Without disposing here, the asyncpg
        # connection(s) opened above stay pooled on the engine, bound to
        # this loop — the next call's *new* loop then fails hard with
        # "got Future ... attached to a different loop" the moment it
        # tries to reuse them. Disposing inside the same loop that owns
        # the connections lets SQLAlchemy close them cleanly and forces a
        # fresh connection next time. See SQLAlchemy's asyncio docs,
        # "Using multiple asyncio event loops".
        await engine.dispose()


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
            provider_id = _send_email(to=user.email, subject=_subject(task, trigger), body=_body(task, user, trigger))
        else:
            provider_id = _send_sms(to=user.phone_number, body=_sms_body(task, trigger))

        log.status = NotificationStatus.SENT
        log.provider_message_id = provider_id
    except Exception as exc:  # noqa: BLE001 — deliberately broad: log any provider failure
        log.status = NotificationStatus.FAILED
        log.error = str(exc)
    finally:
        await db.commit()


def _subject(task: Task, trigger: NotificationTrigger) -> str:
    if trigger == NotificationTrigger.TASK_ASSIGNED:
        # Deliberately doesn't lead with the priority tag the way the
        # created/escalated subjects do — this fires for LOW/MEDIUM
        # tasks too now (see module docstring), and "[LOW] ..." reads
        # like a demoted alert rather than a plain assignment notice.
        return f"You've been assigned {task.ticket_no} — {task.title}"
    return f"[{task.priority.value.upper()}] {task.ticket_no} — {task.title}"


def _body(task: Task, user: User, trigger: NotificationTrigger) -> str:
    first_name = user.full_name.split()[0]
    if trigger == NotificationTrigger.TASK_ASSIGNED:
        return (
            f"Hi {first_name},\n\n"
            f"You've been assigned ticket {task.ticket_no} ({task.priority.value} priority):\n\n"
            f"  {task.title}\n\n"
            f"Due: {task.due_at or 'No due date set'}\n\n"
            f"— HNBG Task Management System"
        )
    return (
        f"Hi {first_name},\n\n"
        f"Ticket {task.ticket_no} ({task.priority.value} priority) needs your attention:\n\n"
        f"  {task.title}\n\n"
        f"Due: {task.due_at or 'No due date set'}\n\n"
        f"— HNBG Task Management System"
    )


def _sms_body(task: Task, trigger: NotificationTrigger) -> str:
    # Keep SMS short — most carriers truncate around 160 chars per segment.
    if trigger == NotificationTrigger.TASK_ASSIGNED:
        return f"[HNBG] You've been assigned {task.ticket_no}: {task.title[:80]}"
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
    Call this from task_service.py for TASK_CREATED / PRIORITY_ESCALATED —
    priority-gated per `should_notify()`. Fire-and-forget, never awaited
    inline in a resolver's critical path. Do NOT use this for
    TASK_ASSIGNED — see `enqueue_assignment_notification` below.
    """
    if should_notify(task.priority):
        send_task_notifications.delay(str(task.id), trigger.value)


def enqueue_assignment_notification(task: Task) -> None:
    """
    Call this from task_service.py whenever a task ends up with a (new)
    assignee — at creation with an assignee already chosen, or on a
    later reassignment. Unlike `enqueue_if_needed`, this is NOT gated by
    `settings.notify_priority_list`: being assigned a task is the "main
    asset" notification of this system (explicit product decision — see
    CHANGELOG.md), so a LOW-priority task assignment notifies the same
    as a URGENT one. Still respects the global NOTIFICATIONS_ENABLED
    kill-switch and, downstream, each recipient's own
    notify_email/notify_sms opt-in.
    """
    if settings.notifications_enabled:
        send_task_notifications.delay(str(task.id), NotificationTrigger.TASK_ASSIGNED.value)
