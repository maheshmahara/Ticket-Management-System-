"""
Business logic for task attachments, kept out of GraphQL resolvers —
same split as app/services/task_service.py.
"""

import base64
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.task import Task
from app.models.task_attachment import TaskAttachment
from app.models.user import User

# ~1.5MB decoded, capped at the base64 (encoded) length since that's what
# arrives over GraphQL before any decoding happens. Generous enough for a
# typical PDF/photo/doc, bounded enough to keep GraphQL payloads and
# Postgres rows sane — this app stores attachments directly in Postgres
# (no object storage anywhere else in the codebase either, see
# User.photo_base64), so an unbounded upload would be a real problem.
MAX_ATTACHMENT_BASE64_LENGTH = 2_000_000

ATTACHMENT_EAGER_LOAD = (selectinload(TaskAttachment.uploaded_by).selectinload(User.department),)


async def add_task_attachment(
    db: AsyncSession, *, actor: User, task: Task, file_name: str, content_type: str, file_base64: str
) -> TaskAttachment:
    decoded = base64.b64decode(file_base64, validate=True)
    attachment = TaskAttachment(
        task_id=task.id,
        uploaded_by_id=actor.id,
        file_name=file_name,
        content_type=content_type,
        file_base64=file_base64,
        file_size_bytes=len(decoded),
    )
    db.add(attachment)
    await db.commit()

    result = await db.execute(
        select(TaskAttachment).options(*ATTACHMENT_EAGER_LOAD).where(TaskAttachment.id == attachment.id)
    )
    return result.scalar_one()


async def get_task_attachment(db: AsyncSession, attachment_id: uuid.UUID) -> TaskAttachment | None:
    result = await db.execute(
        select(TaskAttachment)
        .options(*ATTACHMENT_EAGER_LOAD, selectinload(TaskAttachment.task))
        .where(TaskAttachment.id == attachment_id)
    )
    return result.scalar_one_or_none()


async def delete_task_attachment(db: AsyncSession, *, attachment: TaskAttachment) -> None:
    await db.delete(attachment)
    await db.commit()
