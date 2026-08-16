import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum, ForeignKey, Integer, Sequence, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

# Backs human-readable ticket numbers: TCK-0001, TCK-0002, ...
ticket_number_seq = Sequence("ticket_number_seq", start=1)


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # e.g. "TCK-3021" — generated from ticket_number_seq in the service layer,
    # not directly from the DB default, so we can control the "TCK-" prefix
    # and zero-padding in Python.
    ticket_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # values_callable is required: SQLAlchemy's Enum(SomePyEnum) binds by
    # the Python enum member's *name* by default, not its .value -- but
    # the Postgres enum types (see the Alembic migration) were created
    # with the lowercase .value strings. See app/models/user.py's `role`
    # column for the full explanation; same fix applied here.
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", values_callable=lambda obj: [e.value for e in obj]),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, name="task_priority", values_callable=lambda obj: [e.value for e in obj]),
        default=TaskPriority.MEDIUM,
        nullable=False,
        index=True,
    )

    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False, index=True
    )
    department: Mapped["Department"] = relationship(back_populates="tasks")  # noqa: F821

    # Purely descriptive, unlike department_id — does NOT participate in
    # RBAC scoping (app/graphql/queries.py's `tasks` resolver still scopes
    # by department only). Mirrors User.branch_id exactly; see that
    # column's comment in app/models/user.py. Nullable, no default: most
    # tasks legitimately have no branch set, same reasoning as start_date.
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True
    )
    branch: Mapped["Branch | None"] = relationship()  # noqa: F821

    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    assignee: Mapped["User | None"] = relationship(  # noqa: F821
        back_populates="assigned_tasks", foreign_keys=[assignee_id]
    )

    reporter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reporter: Mapped["User"] = relationship(  # noqa: F821
        back_populates="reported_tasks", foreign_keys=[reporter_id]
    )

    due_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # When work on the task actually begins — distinct from due_at (when
    # it must be finished) and from created_at (when the ticket was
    # filed, which can be well before or after work starts). Powers the
    # left edge of a task's bar on timeline.html's Gantt view. No
    # default, unlike duration_minutes: most existing tasks legitimately
    # have no start date set, and the timeline falls back to created_at
    # client-side rather than backfilling this to a guessed value. See
    # migrations/versions/0004_task_start_date.py.
    start_date: Mapped[datetime | None] = mapped_column(nullable=True)
    # How long the task is expected to take, in minutes — sizes its block
    # on calendar.html's hourly Week grid so time gaps between tasks are
    # real empty space, not guesswork. Defaults to 30 both here (for rows
    # inserted outside the GraphQL API) and in CreateTaskInput (the
    # normal path) — see migrations/versions/0003_task_duration.py.
    duration_minutes: Mapped[int | None] = mapped_column(Integer, default=30, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    comments: Mapped[list["Comment"]] = relationship(  # noqa: F821
        back_populates="task", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["TaskAttachment"]] = relationship(  # noqa: F821
        back_populates="task", cascade="all, delete-orphan"
    )

    @property
    def is_overdue(self) -> bool:
        """
        Computed, not stored — see "Open questions" in
        docs/BACKEND_ARCHITECTURE.md. Avoids a background job having to
        mutate every row when a due date passes.

        Uses `datetime.now(timezone.utc)` rather than the naive
        `datetime.utcnow()` — `self.due_at` is timezone-aware (Postgres
        `TIMESTAMPTZ`, via `Base.type_annotation_map` in
        app/core/database.py), and comparing a naive datetime against
        an aware one raises `TypeError: can't compare offset-naive and
        offset-aware datetimes`. This was the exact same class of bug
        already fixed at the SQL-binding layer for `due_at` — this
        property is a plain Python comparison, not a query, so it needed
        its own fix. Found by actually submitting the Create Task form
        with a due date, not by any import/compile check.
        """
        if self.due_at is None or self.status == TaskStatus.DONE:
            return False
        return datetime.now(timezone.utc) > self.due_at
