"""Add notifications_last_seen_at to users

Revision ID: 0005_notification_seen
Revises: 0004_task_start_date
Create Date: 2026-08-16

Powers the topbar notification bell's unread badge. Rather than a
per-row `is_read` flag on `notification_logs` (a write on every single
notification, plus a migration that has to backfill every existing
row), this uses the simpler "last seen timestamp" pattern: one nullable
column on `users`, set to now() the moment the bell's dropdown is
opened. A notification is "unread" if its created_at is after this
timestamp. NULL correctly means "never opened the bell" — same
semantics as "everything is unread" for a user who's never checked.
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_notification_seen"
down_revision = "0004_task_start_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("notifications_last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "notifications_last_seen_at")
