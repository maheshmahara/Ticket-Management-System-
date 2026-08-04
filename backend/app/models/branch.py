import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Branch(Base):
    """
    A physical location/outlet, e.g. "Headoffice", "Hokkaido Sora",
    "Hokkaido Izakaya", "Janechi/HOMA". Belongs to one BusinessUnit.

    `is_active=False` marks branches that are closed or otherwise
    inactive (none seeded as inactive today, but kept for parity with
    how resigned *staff* are tracked on User.is_active).
    """

    __tablename__ = "branches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    business_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_units.id"), nullable=False
    )
    business_unit: Mapped["BusinessUnit"] = relationship(back_populates="branches")  # noqa: F821

    users: Mapped[list["User"]] = relationship(back_populates="branch")  # noqa: F821
