import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"


class NotificationStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class NotificationTrigger(str, enum.Enum):
    TASK_CREATED = "task_created"
    TASK_ASSIGNED = "task_assigned"
    PRIORITY_ESCALATED = "priority_escalated"
    TASK_OVERDUE = "task_overdue"


class NotificationLog(Base):
    """
    One row per notification attempt (email or SMS), so we can show
    delivery status/history and avoid double-sending. Written by
    app/services/notifications.py, read by any future "notification
    history" admin view.
    """

    __tablename__ = "notification_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task: Mapped["Task"] = relationship()  # noqa: F821

    recipient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    recipient: Mapped["User"] = relationship(back_populates="notifications")  # noqa: F821

    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, name="notification_channel"), nullable=False
    )
    trigger: Mapped[NotificationTrigger] = mapped_column(
        Enum(NotificationTrigger, name="notification_trigger"), nullable=False
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status"), default=NotificationStatus.QUEUED, nullable=False
    )

    # Provider message id (Twilio SID / email Message-ID) for tracing, and
    # the error text on failure — both nullable.
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
