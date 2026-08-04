from dataclasses import dataclass
from typing import Optional

import strawberry
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.fastapi import GraphQLRouter

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.graphql.schema import schema
from app.models.user import User

settings = get_settings()


@dataclass
class GraphQLContext:
    """Attached to every resolver via `info.context`."""

    db: AsyncSession
    user: Optional[User]


async def get_context(request: Request) -> GraphQLContext:
    db = AsyncSessionLocal()
    user = None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        claims = decode_token(auth_header.removeprefix("Bearer "))
        if claims and claims.get("type") == "access":
            # TODO: load the User row by claims["sub"] using `db` and
            # assign it to `user`. Left as a stub since it depends on the
            # models/session wiring being finalized alongside migrations.
            pass

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
