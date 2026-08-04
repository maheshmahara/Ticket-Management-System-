"""
Typed GraphQL errors, per the "Design conventions" note in
docs/BACKEND_ARCHITECTURE.md: every error carries a `code` extension
(e.g. "VALIDATION_ERROR", "FORBIDDEN", "NOT_FOUND", "INVALID_CREDENTIALS")
so the frontend can branch on error type instead of string-matching a
message.
"""

from graphql import GraphQLError


def app_error(code: str, message: str) -> GraphQLError:
    return GraphQLError(message, extensions={"code": code})
