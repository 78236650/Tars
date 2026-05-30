"""Populate request-scoped user/org context from JWT or API key."""

from __future__ import annotations

from typing import Any, Optional

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..context import clear_request_context, set_request_context
from ..gateway.jwt_auth import decode_access_token
from ..org import ORG_ID


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    token = authorization[len(prefix) :].strip()
    return token or None


def _auth_token_store(request: Request) -> Any:
    return getattr(request.app.state, "auth_token_store", None)


def _user_store(request: Request) -> Any:
    return getattr(request.app.state, "user_store", None)


def _try_set_context_from_bearer(request: Request) -> bool:
    """Return True when Authorization is Bearer-shaped (skip API key fallback)."""
    token = _bearer_token(request.headers.get("Authorization"))
    if token is None:
        return False

    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError:
        return True

    jti = claims.get("jti")
    if jti:
        store = _auth_token_store(request)
        if store is not None and store.is_token_revoked(jti):
            return True

    user_id = claims.get("sub")
    if not user_id:
        return True

    org_id = claims.get("org_id") or ORG_ID
    set_request_context(str(user_id), str(org_id))
    return True


def _try_set_context_from_api_key(request: Request) -> None:
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return

    store = _user_store(request)
    if store is None:
        return

    user = store.get_user_by_api_key(api_key)
    if user is None:
        return

    set_request_context(user.id, ORG_ID)


class UserContextMiddleware(BaseHTTPMiddleware):
    """Set contextvars when auth headers are present; always clear after the request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            if not _try_set_context_from_bearer(request):
                _try_set_context_from_api_key(request)
            return await call_next(request)
        finally:
            clear_request_context()
