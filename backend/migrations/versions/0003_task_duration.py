"""Add duration_minutes to tasks

Revision ID: 0003_task_duration
Revises: 0002_user_profile_fields
Create Date: 2026-08-15

Tasks previously only had a single point-in-time `due_at`, no duration —
fine for a due-date list, but meaningless for placing a task as a sized
block on an hourly calendar grid (see prototypes/web/calendar.html).
Defaults to 30 minutes both at the DB level (server_default, for any
row inserted outside the GraphQL API) and in CreateTaskInput (for the
normal path). Existing rows are explicitly backfilled too — Postgres'
server_default on ADD COLUMN only guarantees new rows get it going
forward; the explicit UPDATE removes any doubt for rows that predate
this migration.
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_task_duration"
down_revision = "0002_user_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("duration_minutes", sa.Integer(), nullable=True, server_default="30"),
    )
    op.execute("UPDATE tasks SET duration_minutes = 30 WHERE duration_minutes IS NULL")


def downgrade() -> None:
    op.drop_column("tasks", "duration_minutes")
