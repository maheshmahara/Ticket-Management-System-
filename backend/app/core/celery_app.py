from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "hnbg",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.beat_schedule = {
    # TODO: implement app.services.notifications.send_overdue_digest and
    # point this at it. Runs at 8am daily to notify assignees/managers of
    # newly-overdue tasks. Overdue itself is computed at query time (see
    # Task.is_overdue), so this job is about *notification*, not mutating
    # a stored status. Distinct from send_task_notifications below, which
    # fires immediately on high/urgent task create/assign/escalate rather
    # than on a schedule.
    "send-overdue-digest": {
        "task": "app.services.notifications.send_overdue_digest",
        "schedule": crontab(hour=8, minute=0),
    },
}
celery_app.conf.timezone = "UTC"

# Import task modules so their @celery_app.task decorators register with
# this app. Placed at the bottom (not top) to avoid a circular import,
# since app.services.notifications imports `celery_app` from this module.
from app.services import notifications  # noqa: E402,F401
