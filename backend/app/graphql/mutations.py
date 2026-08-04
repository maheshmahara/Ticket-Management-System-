"""
GraphQL mutation resolvers. Business logic (ticket number generation,
overdue recompute, etc.) belongs in app/services/, not here — resolvers
stay thin: authenticate/authorize, delegate, map to GraphQL types.
"""

import uuid
from typing import Optional

import strawberry
from strawberry.types import Info

from app.core.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.graphql.errors import app_error
from app.graphql.mappers import to_comment, to_task, to_user
from app.graphql.permissions import IsAuthenticated, can_edit_task, can_view_task
from app.graphql.types import (
    AuthPayload,
    Comment,
    CreateTaskInput,
    NotificationPreferencesInput,
    Task,
)
from app.graphql.types import TaskStatus as GqlTaskStatus
from app.graphql.types import UpdateTaskInput, User
from app.models.task import TaskStatus as TaskStatusModel
from app.services import task_service
from app.services.user_service import get_user_by_email, get_user_by_id


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
