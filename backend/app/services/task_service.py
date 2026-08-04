"""
Business logic for tasks, kept out of GraphQL resolvers so it's reusable
from REST endpoints, Celery jobs, or tests without going through GraphQL.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, ticket_number_seq


async def next_ticket_no(db: AsyncSession) -> str:
    """
    Generates the next human-readable ticket number, e.g. "TCK-3021",
    matching the format already shown throughout the UI prototypes.
    """
    result = await db.execute(select(func.nextval(ticket_number_seq.name)))
    n = result.scalar_one()
    return f"TCK-{n:04d}"


async def create_task(db: AsyncSession, *, actor, input) -> Task:
    """
    TODO: implement.
      1. ticket_no = await next_ticket_no(db)
      2. task = Task(ticket_no=ticket_no, reporter_id=actor.id, **input mapped to model fields)
      3. db.add(task); await db.commit(); await db.refresh(task)
      4. return task
    """
    raise NotImplementedError
