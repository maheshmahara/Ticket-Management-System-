import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Role(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable + not unique-enforced at the DB level for staff who don't
    # have a company email on file yet (several rows in the real HNBG
    # roster, e.g. restaurant chefs/drivers) — they can be invited to set
    # one up later. Login is not possible without an email + password.
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # values_callable is required: SQLAlchemy's Enum(SomePyEnum) binds by
    # the Python enum member's *name* ("MEMBER") by default, not its
    # .value ("member") -- but the Postgres enum type (see the Alembic
    # migration) was created with the lowercase .value strings. Without
    # this, every INSERT/UPDATE fails with "invalid input value for enum
    # user_role: MEMBER" (found by actually running scripts/seed_staff.py
    # against a real Postgres instance, not caught by any import/compile
    # check beforehand).
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="user_role", values_callable=lambda obj: [e.value for e in obj]),
        default=Role.MEMBER,
        nullable=False,
    )

    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    department: Mapped["Department"] = relationship(back_populates="users")  # noqa: F821

    # Real-world job title as it appears on the HNBG staff roster, e.g.
    # "chef", "manager", "gm", "driver delivery" — kept verbatim alongside
    # the canonical `department` (see backend/scripts/seed_staff.py for the
    # job-title -> department / RBAC-role mapping used when seeding).
    job_title: Mapped[str | None] = mapped_column(String(150), nullable=True)

    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True
    )
    branch: Mapped["Branch"] = relationship(back_populates="users")  # noqa: F821

    # Hex color for the avatar chip in the UI, e.g. "#1c4b96"
    avatar_color: Mapped[str] = mapped_column(String(7), default="#8e8e93")

    # E.164 format, e.g. "+81901234567" — required for SMS notifications to
    # actually be deliverable; nullable since not every user opts into SMS.
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Per-channel notification opt-in. High/urgent task alerts respect these
    # — see app/services/notifications.py and the "Notifications" section
    # of docs/BACKEND_ARCHITECTURE.md.
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_sms: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Client-resized/compressed avatar photo (see my-profile.html's canvas
    # resize step) — raw base64 payload only, no "data:image/...;base64,"
    # prefix; the frontend adds that prefix when rendering an <img src>.
    photo_base64: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Set once, the first time both department_id and phone_number are
    # present (see update_my_profile in app/graphql/mutations.py, and the
    # equivalent backfill in app/services/org_service.py's admin-facing
    # create_user/update_user) — powers the one-time "complete your
    # profile" redirect gate. Never re-cleared once set, even if
    # department/phone are later blanked out again.
    profile_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Self-requested permission role, pending admin approval. Same
    # values_callable requirement as `role` above (identical Postgres enum
    # type — see that column's comment). Does NOT change what's enforced —
    # only `role` is read by app/graphql/permissions.py. Cleared to None
    # when an admin approves or denies via respondToRoleRequest.
    requested_role: Mapped[Role | None] = mapped_column(
        Enum(Role, name="user_role", values_callable=lambda obj: [e.value for e in obj]),
        nullable=True,
    )

    assigned_tasks: Mapped[list["Task"]] = relationship(  # noqa: F821
        back_populates="assignee", foreign_keys="Task.assignee_id"
    )
    reported_tasks: Mapped[list["Task"]] = relationship(  # noqa: F821
        back_populates="reporter", foreign_keys="Task.reporter_id"
    )
    comments: Mapped[list["Comment"]] = relationship(back_populates="author")  # noqa: F821
    notifications: Mapped[list["NotificationLog"]] = relationship(back_populates="recipient")  # noqa: F821

    @property
    def initials(self) -> str:
        parts = self.full_name.split()
        return "".join(p[0] for p in parts[:2]).upper()
