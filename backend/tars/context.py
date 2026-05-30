"""Request-scoped user/org context (TARS v5.0).

Populated by ``UserContextMiddleware`` from JWT or API key; cleared after each request.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

from fastapi import HTTPException

from .org import ORG_ID

current_user_id: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)
current_org_id: ContextVar[Optional[str]] = ContextVar("current_org_id", default=None)


def get_current_user_id() -> str:
    """Return the authenticated user id for this request."""
    value = current_user_id.get()
    if value is None:
        raise RuntimeError("request context user_id is not set")
    return value


def get_current_org_id() -> str:
    """Return org scope for this request (defaults to ``ORG_ID``)."""
    value = current_org_id.get()
    if value is not None:
        return value
    return ORG_ID


def set_request_context(user_id: str, org_id: str = ORG_ID) -> None:
    current_user_id.set(user_id)
    current_org_id.set(org_id)


def clear_request_context() -> None:
    current_user_id.set(None)
    current_org_id.set(None)


async def require_current_user_id() -> str:
    """FastAPI dependency: authenticated user id from contextvars."""
    try:
        return get_current_user_id()
    except RuntimeError:
        raise HTTPException(status_code=401, detail="Not authenticated")
