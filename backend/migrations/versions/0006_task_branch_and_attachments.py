"""Add branch_id to tasks and a task_attachments table

Revision ID: 0006_task_branch_and_attachments
Revises: 0005_notification_seen
Create Date: 2026-08-16

Two independent additions bundled into one migration since they ship
together:

- tasks.branch_id: nullable, mirrors users.branch_id exactly (see
  app/models/user.py). Purely descriptive — unlike department_id, it
  does not participate in RBAC scoping. No default/backfill: NULL is a
  legitimate, common state, same reasoning as start_date.
- task_attachments: one row per uploaded file, base64 payload stored
  directly in Postgres (this app has no object storage anywhere —
  same approach already used for User.photo_base64). Cascade-deletes
  with its task, same as comments.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_task_branch_and_attachments"
down_revision = "0005_notification_seen"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_tasks_branch_id", "tasks", "branches", ["branch_id"], ["id"])

    op.create_table(
        "task_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_base64", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"]),
    )
    op.create_index("ix_task_attachments_task_id", "task_attachments", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_task_attachments_task_id", table_name="task_attachments")
    op.drop_table("task_attachments")
    op.drop_constraint("fk_tasks_branch_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "branch_id")
