"""Add start_date to tasks

Revision ID: 0004_task_start_date
Revises: 0003_task_duration
Create Date: 2026-08-15

Tasks previously only had `due_at` (when work must be finished) — no
concept of when work actually *begins*. That's fine for a due-date
list, but a Gantt-style timeline (see prototypes/web/timeline.html)
needs both ends of the bar. Unlike `duration_minutes`, there's no
sensible default here: "no start date set" is a legitimate, common
state for most existing tasks, not something to backfill to a
non-null value. Left nullable with no server_default and no backfill
— the timeline falls back to `created_at` client-side for tasks that
never set one.
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_task_start_date"
down_revision = "0003_task_duration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "start_date")
