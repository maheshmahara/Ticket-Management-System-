import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TaskAttachment(Base):
    """
    One row per uploaded file. `file_base64` is the raw payload (no
    data-URI prefix), stored directly in Postgres — same approach as
    User.photo_base64, since this app has no object storage anywhere.
    `file_size_bytes` is the *decoded* size, computed once at upload
    time so the UI can show it without decoding the payload itself.
    """

    __tablename__ = "task_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task: Mapped["Task"] = relationship(back_populates="attachments")  # noqa: F821

    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    uploaded_by: Mapped["User"] = relationship()  # noqa: F821

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_base64: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
