"""
GraphQL mutation resolvers. Business logic (ticket number generation,
overdue recompute, etc.) belongs in app/services/, not here — resolvers
stay thin: authenticate/authorize, delegate, map to GraphQL types.
"""

import base64
import uuid
from datetime import datetime, timezone
from typing import Optional

import strawberry
from strawberry.types import Info

from app.core.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.graphql.errors import app_error
from app.graphql.mappers import (
    to_branch,
    to_business_unit,
    to_comment,
    to_department,
    to_task,
    to_user,
)
from app.graphql.permissions import IsAdmin, IsAuthenticated, can_edit_task, can_view_task
from app.graphql.types import (
    AuthPayload,
    Branch,
    BulkTaskUpdateInput,
    BulkUpdateFailure,
    BulkUpdateResult,
    BusinessUnit,
    Comment,
    CreateBranchInput,
    CreateTaskInput,
    CreateUserInput,
    Department,
    NotificationPreferencesInput,
    Task,
    UpdateBranchInput,
    UpdateMyProfileInput,
    UpdateUserInput,
)
from app.graphql.types import Role as GqlRole
from app.graphql.types import TaskStatus as GqlTaskStatus
from app.graphql.types import UpdateTaskInput, User
from app.models.task import TaskPriority as TaskPriorityModel
from app.models.task import TaskStatus as TaskStatusModel
from app.models.user import Role as RoleModel
from app.services import org_service, task_service
from app.services.user_service import get_user_by_email, get_user_by_id

# Defense in depth, not the primary control — the client resizes to
# ~200x200 JPEG q=0.7 first (see my-profile.html), which produces roughly
# 10-30KB of base64. 500,000 chars (~366KB decoded) leaves generous
# headroom for unusual images while still rejecting a raw multi-MB upload
# that bypassed client-side resize entirely.
MAX_PHOTO_BASE64_LENGTH = 500_000


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def login(self, info: Info, email: str, password: str) -> AuthPayload:
        db = info.context.db
        user = await get_user_by_email(db, email)

        if user is None or not user.password_hash or not verify_password(password, user.password_hash):
            raise app_error("INVALID_CREDENTIALS", "Invalid email or password.")
        if not user.is_active:
            raise app_error("FORBIDDEN", "This account is inactive.")

        access_token = create_access_token(str(user.id), {"role": user.role.value})
        refresh_token = create_refresh_token(str(user.id))
        return AuthPayload(access_token=access_token, refresh_token=refresh_token, user=to_user(user))

    @strawberry.mutation
    async def refresh_token(self, info: Info, token: str) -> AuthPayload:
        claims = decode_token(token)
        if claims is None or claims.get("type") != "refresh":
            raise app_error("INVALID_TOKEN", "Invalid or expired refresh token.")

        try:
            user_id = uuid.UUID(claims["sub"])
        except (KeyError, ValueError):
            raise app_error("INVALID_TOKEN", "Invalid or expired refresh token.")

        db = info.context.db
        user = await get_user_by_id(db, user_id)
        if user is None or not user.is_active:
            raise app_error("INVALID_TOKEN", "Invalid or expired refresh token.")

        access_token = create_access_token(str(user.id), {"role": user.role.value})
        new_refresh_token = create_refresh_token(str(user.id))
        return AuthPayload(access_token=access_token, refresh_token=new_refresh_token, user=to_user(user))

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def create_task(self, info: Info, input: CreateTaskInput) -> Task:
        db = info.context.db
        task = await task_service.create_task(db, actor=info.context.user, input=input)
        return to_task(task)

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def update_task(self, info: Info, id: strawberry.ID, input: UpdateTaskInput) -> Task:
        db = info.context.db
        actor = info.context.user

        task = await task_service.get_task(db, uuid.UUID(str(id)))
        if task is None:
            raise app_error("NOT_FOUND", "Task not found.")
        if not can_edit_task(actor, task):
            raise app_error("FORBIDDEN", "You don't have permission to edit this task.")

        task = await task_service.update_task(db, actor=actor, task=task, input=input)
        return to_task(task)

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def assign_task(
        self, info: Info, id: strawberry.ID, assignee_id: Optional[strawberry.ID] = None
    ) -> Task:
        db = info.context.db
        actor = info.context.user

        task = await task_service.get_task(db, uuid.UUID(str(id)))
        if task is None:
            raise app_error("NOT_FOUND", "Task not found.")
        if not can_edit_task(actor, task):
            raise app_error("FORBIDDEN", "You don't have permission to assign this task.")

        new_assignee_id = uuid.UUID(str(assignee_id)) if assignee_id else None
        # Members may only assign to themselves — see the RBAC matrix in
        # docs/BACKEND_ARCHITECTURE.md.
        if actor.role.value == "member" and new_assignee_id != actor.id:
            raise app_error("FORBIDDEN", "Members may only assign tasks to themselves.")

        task = await task_service.assign_task(db, task=task, assignee_id=new_assignee_id)
        return to_task(task)

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def change_task_status(
        self, info: Info, id: strawberry.ID, status: GqlTaskStatus
    ) -> Task:
        db = info.context.db
        actor = info.context.user

        task = await task_service.get_task(db, uuid.UUID(str(id)))
        if task is None:
            raise app_error("NOT_FOUND", "Task not found.")
        if not can_edit_task(actor, task):
            raise app_error("FORBIDDEN", "You don't have permission to update this task.")

        task = await task_service.change_task_status(db, task=task, status=TaskStatusModel(status.value))
        return to_task(task)

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def bulk_update_tasks(
        self, info: Info, ids: list[strawberry.ID], input: BulkTaskUpdateInput
    ) -> BulkUpdateResult:
        """Field-level gate is just IsAuthenticated, same as the
        single-task mutations above — the real authorization is the
        per-task can_edit_task check inside task_service.bulk_update_tasks,
        since a Member legitimately needs to bulk-update their own tasks."""
        if not ids:
            raise app_error("VALIDATION_ERROR", "Select at least one task.")
        if input.status is None and input.priority is None and input.assignee_id is None:
            raise app_error("VALIDATION_ERROR", "Choose a status, assignee, or priority to apply.")

        db = info.context.db
        actor = info.context.user

        failures, updated = await task_service.bulk_update_tasks(
            db,
            actor=actor,
            task_ids=[uuid.UUID(str(i)) for i in ids],
            status=TaskStatusModel(input.status.value) if input.status is not None else None,
            priority=TaskPriorityModel(input.priority.value) if input.priority is not None else None,
            assignee_id=uuid.UUID(str(input.assignee_id)) if input.assignee_id is not None else None,
        )
        return BulkUpdateResult(
            success_count=len(updated),
            failures=[BulkUpdateFailure(id=strawberry.ID(str(fid)), reason=reason) for fid, reason in failures],
            tasks=[to_task(t) for t in updated],
        )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def delete_task(self, info: Info, id: strawberry.ID) -> bool:
        db = info.context.db
        actor = info.context.user

        task = await task_service.get_task(db, uuid.UUID(str(id)))
        if task is None:
            raise app_error("NOT_FOUND", "Task not found.")
        if not can_edit_task(actor, task):
            raise app_error("FORBIDDEN", "You don't have permission to delete this task.")

        await task_service.delete_task(db, task=task)
        return True

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def add_comment(self, info: Info, task_id: strawberry.ID, body: str) -> Comment:
        db = info.context.db
        actor = info.context.user

        task = await task_service.get_task(db, uuid.UUID(str(task_id)))
        if task is None:
            raise app_error("NOT_FOUND", "Task not found.")
        if not can_view_task(actor, task):
            raise app_error("FORBIDDEN", "You don't have access to this task.")
        if not body.strip():
            raise app_error("VALIDATION_ERROR", "Comment body can't be empty.")

        comment = await task_service.add_comment(db, actor=actor, task=task, body=body.strip())
        return to_comment(comment)

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def update_notification_preferences(self, info: Info, input: NotificationPreferencesInput) -> User:
        db = info.context.db
        actor = info.context.user

        will_have_sms = input.notify_sms if input.notify_sms is not None else actor.notify_sms
        will_have_phone = input.phone_number if input.phone_number is not None else actor.phone_number
        if will_have_sms and not will_have_phone:
            raise app_error("VALIDATION_ERROR", "A phone number is required to enable SMS notifications.")

        if input.phone_number is not None:
            actor.phone_number = input.phone_number
        if input.notify_email is not None:
            actor.notify_email = input.notify_email
        if input.notify_sms is not None:
            actor.notify_sms = input.notify_sms

        await db.commit()
        await db.refresh(actor, attribute_names=["phone_number", "notify_email", "notify_sms"])
        return to_user(actor)

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def update_my_profile(self, info: Info, input: UpdateMyProfileInput) -> User:
        """Self-service department/job title/phone/photo editing — see
        UpdateMyProfileInput's docstring for why permission Role isn't
        here (that's requestRoleChange, which needs admin approval).
        Also the mutation that flips on profile_completed_at, the first
        time department + phone are both present, powering the one-time
        onboarding-gate redirect on every other page."""
        db = info.context.db
        actor = info.context.user

        if input.photo_base64 is not None and input.remove_photo:
            raise app_error("VALIDATION_ERROR", "Can't upload a new photo and remove the photo in the same request.")

        if input.photo_base64 is not None:
            if len(input.photo_base64) > MAX_PHOTO_BASE64_LENGTH:
                raise app_error("VALIDATION_ERROR", "Photo is too large — please use a smaller image.")
            try:
                base64.b64decode(input.photo_base64, validate=True)
            except Exception:
                raise app_error("VALIDATION_ERROR", "Photo isn't valid base64 image data.")
            actor.photo_base64 = input.photo_base64
        elif input.remove_photo:
            actor.photo_base64 = None

        if input.department_id is not None:
            actor.department_id = uuid.UUID(str(input.department_id))
        if input.job_title is not None:
            actor.job_title = input.job_title
        if input.phone_number is not None:
            actor.phone_number = input.phone_number

        if actor.profile_completed_at is None and actor.department_id is not None and actor.phone_number:
            actor.profile_completed_at = datetime.now(timezone.utc)

        await db.commit()
        # department may have just changed — re-fetch fully eager-loaded
        # rather than a narrow db.refresh(attribute_names=...), since
        # to_user() also reads the department/branch relationships.
        return to_user(await get_user_by_id(db, actor.id))

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def request_role_change(self, info: Info, role: Optional[GqlRole] = None) -> User:
        """Self-service request for a different permission Role — does
        NOT change what's enforced (see app/models/user.py's `role`
        column comment). An admin must approve it via
        respondToRoleRequest before it takes effect. Pass role=null to
        withdraw a pending request without waiting for an admin to deny
        it."""
        db = info.context.db
        actor = info.context.user

        if role is not None and role.value == actor.role.value:
            raise app_error("VALIDATION_ERROR", "You already have this role.")

        actor.requested_role = RoleModel(role.value) if role is not None else None
        await db.commit()
        await db.refresh(actor, attribute_names=["requested_role"])
        return to_user(actor)

    # --- Admin panel mutations (permission_classes=[IsAdmin]) ---

    @strawberry.mutation(permission_classes=[IsAdmin])
    async def create_department(self, info: Info, name: str) -> Department:
        db = info.context.db
        if not name.strip():
            raise app_error("VALIDATION_ERROR", "Department name can't be empty.")
        department = await org_service.create_department(db, name=name)
        return to_department(department)

    @strawberry.mutation(permission_classes=[IsAdmin])
    async def create_business_unit(self, info: Info, name: str) -> BusinessUnit:
        db = info.context.db
        if not name.strip():
            raise app_error("VALIDATION_ERROR", "Business unit name can't be empty.")
        business_unit = await org_service.create_business_unit(db, name=name)
        return to_business_unit(business_unit)

    @strawberry.mutation(permission_classes=[IsAdmin])
    async def create_branch(self, info: Info, input: CreateBranchInput) -> Branch:
        db = info.context.db
        if not input.name.strip():
            raise app_error("VALIDATION_ERROR", "Branch name can't be empty.")
        branch = await org_service.create_branch(
            db,
            name=input.name,
            business_unit_id=uuid.UUID(str(input.business_unit_id)),
            is_active=input.is_active,
        )
        return to_branch(branch)

    @strawberry.mutation(permission_classes=[IsAdmin])
    async def update_branch(self, info: Info, id: strawberry.ID, input: UpdateBranchInput) -> Branch:
        db = info.context.db
        branch = await org_service.update_branch(
            db, branch_id=uuid.UUID(str(id)), name=input.name, is_active=input.is_active
        )
        return to_branch(branch)

    @strawberry.mutation(permission_classes=[IsAdmin])
    async def create_user(self, info: Info, input: CreateUserInput) -> User:
        db = info.context.db
        if not input.full_name.strip():
            raise app_error("VALIDATION_ERROR", "Full name can't be empty.")
        if not input.password or len(input.password) < 6:
            raise app_error("VALIDATION_ERROR", "Password must be at least 6 characters.")
        user = await org_service.create_user(db, input=input)
        return to_user(user)

    @strawberry.mutation(permission_classes=[IsAdmin])
    async def update_user(self, info: Info, id: strawberry.ID, input: UpdateUserInput) -> User:
        db = info.context.db
        actor = info.context.user

        # Guard against an admin locking themselves out by demoting or
        # deactivating their own account — there'd be no one left who could
        # undo it via the admin panel itself.
        if str(id) == str(actor.id):
            if input.is_active is False:
                raise app_error("VALIDATION_ERROR", "You can't deactivate your own account.")
            if input.role is not None and input.role.value != "admin":
                raise app_error("VALIDATION_ERROR", "You can't remove your own admin role.")

        user = await org_service.update_user(db, user_id=uuid.UUID(str(id)), input=input)
        return to_user(user)

    @strawberry.mutation(permission_classes=[IsAdmin])
    async def respond_to_role_request(self, info: Info, user_id: strawberry.ID, approve: bool) -> User:
        db = info.context.db
        actor = info.context.user

        user = await get_user_by_id(db, uuid.UUID(str(user_id)))
        if user is None:
            raise app_error("NOT_FOUND", "User not found.")
        if user.requested_role is None:
            raise app_error("VALIDATION_ERROR", "This user has no pending role request.")

        if approve:
            # Same self-lockout guard as update_user above — an admin
            # approving their own downgrade request would leave no one
            # able to undo it via the admin panel.
            if str(user.id) == str(actor.id) and user.requested_role != RoleModel.ADMIN:
                raise app_error("VALIDATION_ERROR", "You can't remove your own admin role, even via a role request.")
            user.role = user.requested_role
        user.requested_role = None

        await db.commit()
        return to_user(await get_user_by_id(db, user.id))

    @strawberry.mutation(permission_classes=[IsAdmin])
    async def reset_user_password(self, info: Info, id: strawberry.ID, new_password: str) -> bool:
        db = info.context.db
        if not new_password or len(new_password) < 6:
            raise app_error("VALIDATION_ERROR", "Password must be at least 6 characters.")
        await org_service.reset_user_password(db, user_id=uuid.UUID(str(id)), new_password=new_password)
        return True
