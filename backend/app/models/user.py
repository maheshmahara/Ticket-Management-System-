import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, String
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
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), default=Role.MEMBER, nullable=False)

    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    department: Mapped["Department"] = relationship(back_populates="users")  # noqa: F821

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
