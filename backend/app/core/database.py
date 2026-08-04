from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.environment == "development")

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """
    Base class for all ORM models.

    `type_annotation_map` makes every bare `Mapped[datetime]` /
    `Mapped[datetime | None]` column timezone-aware (Postgres
    `TIMESTAMP WITH TIME ZONE`) without each model having to spell out
    `mapped_column(DateTime(timezone=True))` individually. Without
    this, SQLAlchemy infers a *naive* `DateTime()` for a bare `datetime`
    annotation — which doesn't match the Alembic migration's
    `sa.DateTime(timezone=True)` columns, and asyncpg rejects any
    timezone-aware Python datetime (e.g. anything parsed from a
    GraphQL `DateTime` scalar sent by a real client) against that
    naive-typed bind parameter with "can't subtract offset-naive and
    offset-aware datetimes". Found by actually submitting a due date
    from the wired-up frontend, not by any import/compile check.
    """

    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI/Strawberry dependency that yields a request-scoped DB session."""
    async with AsyncSessionLocal() as session:
        yield session
