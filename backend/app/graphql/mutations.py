"""
GraphQL mutation resolvers. Business logic (ticket number generation,
overdue recompute, etc.) belongs in app/services/, not here — resolvers
should stay thin: authenticate/authorize, delegate, map to GraphQL types.
"""

from typing import Optional

import strawberry
from strawberry.types import Info

from app.core.security import decode_token  # create_access_token/create_refresh_token: see login() TODO
from app.graphql.permissions import IsAuthenticated
from app.graphql.types import AuthPayload, Comment, CreateTaskInput, Task, TaskStatus, UpdateTaskInput


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def login(self, info: Info, email: str, password: str) -> AuthPayload:
        # TODO:
        #  1. Look up UserModel by email via info.context.db
        #  2. verify_password(password, user.password_hash) — raise a
        #     typed GraphQL error (code: "INVALID_CREDENTIALS") if it fails
        #  3. issue create_access_token(str(user.id), {"role": user.role})
        #     and create_refresh_token(str(user.id))
        #  4. map user -> User GraphQL type, return AuthPayload
        raise NotImplementedError

    @strawberry.mutation
    async def refresh_token(self, info: Info, token: str) -> AuthPayload:
        claims = decode_token(token)
        if claims is None or claims.get("type") != "refresh":
            raise ValueError("Invalid or expired refresh token")
        # TODO: reload the user by claims["sub"], reissue both tokens.
        raise NotImplementedError

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def create_task(self, info: Info, input: CreateTaskInput) -> Task:
        # TODO: delegate to app.services.task_service.create_task(db, actor=info.context.user, input=input)
        # which is responsible for: generating the next ticket_no, defaulting
        # reporter_id to the current user, persisting, and returning the row.
        raise NotImplementedError

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def update_task(self, info: Info, id: strawberry.ID, input: UpdateTaskInput) -> Task:
        # TODO: load task, check can_edit_task(info.context.user, task)
        # from app.graphql.permissions, apply changes, persist.
        raise NotImplementedError

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def assign_task(self, info: Info, id: strawberry.ID, assignee_id: Optional[strawberry.ID] = None) -> Task:
        # TODO: Members may only assign to themselves (see RBAC matrix in
        # docs/BACKEND_ARCHITECTURE.md) — enforce that here or in the
        # service layer before persisting.
        raise NotImplementedError

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def change_task_status(self, info: Info, id: strawberry.ID, status: TaskStatus) -> Task:
        # TODO: load task, update status, set completed_at when moving to
        # DONE (and clear it if moved back out of DONE), persist.
        raise NotImplementedError

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def delete_task(self, info: Info, id: strawberry.ID) -> bool:
        # TODO: load task, check can_edit_task, delete, return True.
        raise NotImplementedError

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def add_comment(self, info: Info, task_id: strawberry.ID, body: str) -> Comment:
        # TODO: verify the task exists and the actor can view it, persist
        # a Comment row with author_id=info.context.user.id.
        raise NotImplementedError
