import uuid
from dataclasses import dataclass
from typing import Optional

import strawberry
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.fastapi import GraphQLRouter

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_token
from app.graphql.schema import schema
from app.models.user import User
from app.services.user_service import get_user_by_id

settings = get_settings()


@dataclass
class GraphQLContext:
    """Attached to every resolver via `info.context`."""

    db: AsyncSession
    user: Optional[User]


async def get_context(request: Request, db: AsyncSession = Depends(get_db)) -> GraphQLContext:
    """
    `db` is a FastAPI-managed dependency (see app.core.database.get_db) —
    FastAPI closes it once the request finishes, so this resolver doesn't
    need to manage the session's lifecycle itself.
    """
    user = None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        claims = decode_token(auth_header.removeprefix("Bearer "))
        if claims and claims.get("type") == "access":
            try:
                user_id = uuid.UUID(claims["sub"])
            except (KeyError, ValueError, TypeError):
                user_id = None

            if user_id is not None:
                candidate = await get_user_by_id(db, user_id)
                if candidate is not None and candidate.is_active:
                    user = candidate

    return GraphQLContext(db=db, user=user)


graphql_router = GraphQLRouter(schema, context_getter=get_context)

app = FastAPI(title="HNBG Task Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graphql_router, prefix="/graphql")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
