"""Add self-service profile fields (photo, completion gate, role request)

Revision ID: 0002_user_profile_fields
Revises: 0001_initial_schema
Create Date: 2026-08-15

Three new nullable columns on `users`:
  - photo_base64: client-resized profile photo (see my-profile.html's
    canvas resize step), raw base64 payload with no data-URI prefix.
  - profile_completed_at: set once, the first time a user has both a
    department and a phone number on file — powers the one-time
    "complete your profile" login gate. Never re-cleared once set.
  - requested_role: a self-requested permission-role change, pending
    admin approval. Does NOT affect what's enforced (only the existing
    `role` column does) until an admin approves it via
    respondToRoleRequest.

Existing rows that already satisfy the completion criteria are backfilled
below so no currently-working account gets retroactively forced through
onboarding just because this migration ran.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_user_profile_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

# Reuses the `user_role` enum type created in 0001 (identical
# admin/manager/member members) rather than a second enum type.
# create_type=False tells Alembic the Postgres type already exists, so
# this doesn't try (and fail) to CREATE TYPE user_role a second time.
_user_role_enum = postgresql.ENUM(
    "admin", "manager", "member", name="user_role", create_type=False
)


def upgrade() -> None:
    op.add_column("users", sa.Column("photo_base64", sa.Text(), nullable=True))
    op.add_column(
        "users", sa.Column("profile_completed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("requested_role", _user_role_enum, nullable=True))

    op.execute(
        """
        UPDATE users
        SET profile_completed_at = now()
        WHERE department_id IS NOT NULL
          AND phone_number IS NOT NULL
          AND profile_completed_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("users", "requested_role")
    op.drop_column("users", "profile_completed_at")
    op.drop_column("users", "photo_base64")
