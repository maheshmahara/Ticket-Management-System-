import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class BusinessUnit(Base):
    """
    Top level of HNBG's real org structure, e.g. "Overall" (head office
    functions), "Restaurants", "Trading". One level above Branch.

    Introduced when seeding the real HNBG staff roster (see
    backend/seed_data/staff.json and backend/scripts/seed_staff.py) —
    the original schema only had a flat Department, which wasn't enough
    to represent branch/business-unit reporting lines.
    """

    __tablename__ = "business_units"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    branches: Mapped[list["Branch"]] = relationship(back_populates="business_unit")  # noqa: F821
