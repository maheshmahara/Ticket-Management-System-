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
class BusinessUnitRef:
    """Lightweight BusinessUnit reference (no nested `branches`), used from
    Branch.business_unit — breaks what would otherwise be an infinite
    Branch -> BusinessUnit -> branches -> Branch -> ... cycle, since these
    GraphQL types are plain dataclasses built eagerly by app/graphql/mappers.py
    (not lazy per-field resolvers), so any real cycle would recurse forever
    at mapping time rather than just being an unused schema edge."""

    id: strawberry.ID
    name: str


@strawberry.type
class Branch:
    """A physical location/outlet, one level under BusinessUnit."""

    id: strawberry.ID
    name: str
    is_active: bool
    business_unit: BusinessUnitRef


@strawberry.type
class BusinessUnit:
    """Top level of HNBG's real org structure, e.g. "Overall", "Restaurants",
    "Trading" — see app/models/business_unit.py for the full rationale."""

    id: strawberry.ID
    name: str
    branches: list[Branch]


@strawberry.type
class User:
    id: strawberry.ID
    # Nullable: several seeded HNBG staff (see backend/seed_data/staff.json)
    # have no company email on file yet and can't log in until one is set.
    email: Optional[str]
    full_name: str
    role: Role
    department: Optional[Department]
    # Real-world job title from the HNBG roster (e.g. "chef", "gm",
    # "driver delivery") — see app/models/user.py for why this is kept
    # verbatim alongside the canonical `department`.
    job_title: Optional[str]
    branch: Optional[Branch]
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
class UserWorkload:
    """Powers the Kanban board's inline assignee picker — how many open
    (not-DONE) tickets each candidate assignee already has, platform-wide,
    regardless of which department's board is being viewed."""

    user: User
    open_task_count: int


@strawberry.type
class BulkUpdateFailure:
    id: strawberry.ID
    # "NOT_FOUND" | "FORBIDDEN" — mirrors app/graphql/errors.py's error
    # codes, but this is a per-item result inside an otherwise-successful
    # response, not a top-level GraphQL error.
    reason: str


@strawberry.type
class BulkUpdateResult:
    """Bulk actions are partial-success, not all-or-nothing: a selection
    can legitimately mix tasks you can and can't edit (e.g. a Manager
    viewing — but not able to edit — a cross-department task assigned to
    them), so one un-editable row shouldn't block everything else."""

    success_count: int
    failures: list[BulkUpdateFailure]
    tasks: list[Task]


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
    # Used by the "My Tasks" sidebar badge to count only tasks still
    # outstanding (anything not DONE), without callers having to spell
    # out `status != DONE` — there's no single TaskStatus value for
    # "not done" since NOT_DONE isn't a real status.
    exclude_done: Optional[bool] = None


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
class BulkTaskUpdateInput:
    """Applied to every task in a bulkUpdateTasks(ids, input) call. Same
    "None means leave unchanged" convention as UpdateTaskInput — this is
    NOT how you'd unassign a task in bulk (that's not a requirement here),
    just how you skip a field you don't want this bulk action to touch."""

    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assignee_id: Optional[strawberry.ID] = None


@strawberry.input
class NotificationPreferencesInput:
    """User's own notification opt-in/out — see the Notifications section
    of docs/BACKEND_ARCHITECTURE.md. phone_number is required if notify_sms
    is being set to true and the user has none on file."""

    phone_number: Optional[str] = None
    notify_email: Optional[bool] = None
    notify_sms: Optional[bool] = None


# --- Admin panel inputs ---
# Everything below is used only by mutations gated with
# permission_classes=[IsAdmin] in app/graphql/mutations.py.


@strawberry.input
class CreateUserInput:
    full_name: str
    # A temp/initial password the admin sets directly, matching the
    # existing scripts/set_password.py pattern — there's no email-invite
    # flow yet (see backend/README.md's "Remaining known gaps"), so admin
    # user creation has to hand the person *something* to log in with.
    password: str
    email: Optional[str] = None
    role: Role = Role.MEMBER
    department_id: Optional[strawberry.ID] = None
    branch_id: Optional[strawberry.ID] = None
    job_title: Optional[str] = None
    phone_number: Optional[str] = None


@strawberry.input
class UpdateUserInput:
    full_name: Optional[str] = None
    role: Optional[Role] = None
    department_id: Optional[strawberry.ID] = None
    branch_id: Optional[strawberry.ID] = None
    job_title: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: Optional[bool] = None
    notify_email: Optional[bool] = None
    notify_sms: Optional[bool] = None


@strawberry.input
class CreateBranchInput:
    name: str
    business_unit_id: strawberry.ID
    is_active: bool = True


@strawberry.input
class UpdateBranchInput:
    name: Optional[str] = None
    is_active: Optional[bool] = None
