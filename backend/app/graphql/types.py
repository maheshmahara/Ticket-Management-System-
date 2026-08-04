"""
Strawberry GraphQL types. These mirror schema.graphql (see that file for the
SDL reference / rationale). Field names are camelCase in GraphQL automatically
via Strawberry's default auto_camel_case behavior on these snake_case attrs.
"""

import enum
from datetime import datetime
from typing import Optional

import strawberry


@strawberry.enum
class Role(enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"


@strawberry.enum
class TaskStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


@strawberry.enum
class TaskPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@strawberry.type
class Department:
    id: strawberry.ID
    name: str


@strawberry.type
class User:
    id: strawberry.ID
    email: str
    full_name: str
    role: Role
    department: Optional[Department]
    avatar_color: str
    initials: str
    is_active: bool
    phone_number: Optional[str]
    notify_email: bool
    notify_sms: bool


@strawberry.type
class Comment:
    id: strawberry.ID
    body: str
    author: User
    created_at: datetime


@strawberry.type
class Task:
    id: strawberry.ID
    ticket_no: str
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    department: Department
    assignee: Optional[User]
    reporter: User
    due_at: Optional[datetime]
    is_overdue: bool
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    comments: list[Comment]


@strawberry.type
class PageInfo:
    has_next_page: bool
    end_cursor: Optional[str]


@strawberry.type
class TaskEdge:
    cursor: str
    node: Task


@strawberry.type
class TaskConnection:
    edges: list[TaskEdge]
    page_info: PageInfo
    total_count: int


@strawberry.type
class DashboardStats:
    """Powers the four dashboard status tiles: Pending / In Progress / Overdue / Completed."""

    pending: int
    in_progress: int
    overdue: int
    completed: int


@strawberry.type
class AuthPayload:
    access_token: str
    refresh_token: str
    user: User


@strawberry.input
class TaskFilterInput:
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    department_id: Optional[strawberry.ID] = None
    assignee_id: Optional[strawberry.ID] = None
    search: Optional[str] = None


@strawberry.input
class TaskSortInput:
    field: str  # "createdAt" | "dueAt" | "priority"
    direction: str  # "ASC" | "DESC"


@strawberry.input
class PageInput:
    first: Optional[int] = 25
    after: Optional[str] = None


@strawberry.input
class CreateTaskInput:
    title: str
    description: Optional[str] = None
    department_id: strawberry.ID
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    due_at: Optional[datetime] = None
    assignee_id: Optional[strawberry.ID] = None


@strawberry.input
class UpdateTaskInput:
    title: Optional[str] = None
    description: Optional[str] = None
    department_id: Optional[strawberry.ID] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    due_at: Optional[datetime] = None
    assignee_id: Optional[strawberry.ID] = None


@strawberry.input
class NotificationPreferencesInput:
    """User's own notification opt-in/out — see the Notifications section
    of docs/BACKEND_ARCHITECTURE.md. phone_number is required if notify_sms
    is being set to true and the user has none on file."""

    phone_number: Optional[str] = None
    notify_email: Optional[bool] = None
    notify_sms: Optional[bool] = None
