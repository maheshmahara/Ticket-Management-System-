import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Department(Base):
    """
    e.g. Engineering, Product, Design, Marketing, Sales, Finance,
    Human Resources, IT & Operations — matches the options in
    prototypes/web/create-task.html's Department field.
    """

    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="department")  # noqa: F821
    tasks: Mapped[list["Task"]] = relationship(back_populates="department")  # noqa: F821
