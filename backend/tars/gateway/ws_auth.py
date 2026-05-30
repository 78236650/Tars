"""WebSocket authentication (JWT query token or API key)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException, WebSocket

from ..api._auth import Principal, resolve_authenticated_principal
from ..context import clear_request_context, set_request_context
from ..org import ORG_ID


def _query_token(websocket: WebSocket) -> Optional[str]:
    token = (websocket.query_params.get("token") or "").strip()
    return token or None


def _query_api_key(websocket: WebSocket) -> Optional[str]:
    key = (websocket.query_params.get("api_key") or "").strip()
    if key:
        return key
    header = (websocket.headers.get("x-api-key") or "").strip()
    return header or None


def resolve_websocket_principal(
    websocket: WebSocket,
    *,
    user_store: Any,
    auth_token_store: Any = None,
) -> Principal:
    """Validate WS credentials; raises HTTPException on failure."""
    token = _query_token(websocket)
    authorization = f"Bearer {token}" if token else None
    return resolve_authenticated_principal(
        _query_api_key(websocket),
        None,
        None,
        user_store,
        authorization=authorization,
        auth_token_store=auth_token_store,
    )


async def close_websocket_unauthorized(
    websocket: WebSocket,
    *,
    code: int = 4401,
    reason: str = "Unauthorized",
) -> None:
    try:
        await websocket.close(code=code, reason=reason[:123])
    except Exception:
        pass


async def authenticate_websocket(
    websocket: WebSocket,
    *,
    user_store: Any,
    auth_token_store: Any = None,
    require_auth: bool = True,
) -> Optional[Principal]:
    """Authenticate WS; set request context for the connection handler.

    Returns None after closing the socket when auth fails or is missing.
    """
    token = _query_token(websocket)
    api_key = _query_api_key(websocket)
    if require_auth and not token and not api_key:
        await close_websocket_unauthorized(websocket, reason="Missing authentication")
        return None

    if not token and not api_key:
        return None

    try:
        principal = resolve_websocket_principal(
            websocket,
            user_store=user_store,
            auth_token_store=auth_token_store,
        )
    except HTTPException as exc:
        detail = str(exc.detail) if exc.detail else "Unauthorized"
        await close_websocket_unauthorized(websocket, reason=detail)
        return None

    set_request_context(principal.user_id, ORG_ID)
    return principal
