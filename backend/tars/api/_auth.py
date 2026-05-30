"""Centralized authentication dependency for all FastAPI routers.

Replaces the per-route ``except Exception: return`` anti-pattern with a single
source of truth for principal resolution. All routes that previously read
``Authorization`` / ``X-API-Key`` / ``X-User-Role`` / ``X-Tenant-Id`` headers
should depend on ``require_authenticated_user`` (or ``require_admin`` /
``require_module(name)``) instead.

Auth model:

- ``Authorization: Bearer <jwt>`` **or** ``X-API-Key`` is required. Missing both
  -> 401. When Bearer is present (non-empty token), JWT is tried exclusively;
  invalid Bearer must **not** fall through to the api key.
- ``X-User-Role: admin`` is a client-controlled hint. It is honoured **only**
  when the resolved user is ``admin``. A non-admin sending the header -> 403.
- ``tenant_id`` on ``Principal`` is the **organization scope** (v5.0: always
  ``org_default`` from ``tars.org.ORG_ID``). Per-user privacy uses ``user_id``.
- ``X-Tenant-Id`` is **ignored** (single-org deployment; no SaaS impersonation).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import jwt
from fastapi import Depends, Header, HTTPException

from ..gateway.jwt_auth import decode_access_token
from ..org import ORG_ID


def _normalize_role(role: Any) -> str:
    """Coerce DB enum / string role to lowercase slug (e.g. ``admin``)."""
    if role is None:
        return "user"
    if isinstance(role, Enum):
        return str(role.value).lower()
    return str(role).lower()


def _is_admin_role(role: Any) -> bool:
    return _normalize_role(role) == "admin"


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    token = authorization[len(prefix) :].strip()
    return token or None


def _principal_from_jwt(
    token: str,
    role_header: Optional[str],
    user_store: Any,
    auth_token_store: Any,
) -> Principal:
    if user_store is None:
        raise HTTPException(status_code=503, detail="auth subsystem not initialized")

    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    jti = claims.get("jti")
    if jti and auth_token_store is not None and auth_token_store.is_token_revoked(jti):
        raise HTTPException(status_code=401, detail="Token revoked")

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = user_store.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    role_value = _normalize_role(getattr(user, "role", None))
    is_admin = _is_admin_role(getattr(user, "role", None))

    if role_header == "admin" and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="X-User-Role admin requires admin api key",
        )

    return Principal(
        user_id=user.id,
        role=role_value,
        role_template_id=getattr(user, "role_template_id", None) or "standard",
        tenant_id=ORG_ID,
        is_admin=is_admin,
        api_key=getattr(user, "api_key", None) or "",
    )


def _principal_from_api_key(
    api_key: str,
    role_header: Optional[str],
    user_store: Any,
) -> Principal:
    if user_store is None:
        raise HTTPException(status_code=503, detail="auth subsystem not initialized")

    user = user_store.get_user_by_api_key(api_key)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    role_value = _normalize_role(getattr(user, "role", None))
    is_admin = _is_admin_role(getattr(user, "role", None))

    if role_header == "admin" and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="X-User-Role admin requires admin api key",
        )

    return Principal(
        user_id=user.id,
        role=role_value,
        role_template_id=getattr(user, "role_template_id", None) or "standard",
        tenant_id=ORG_ID,
        is_admin=is_admin,
        api_key=api_key,
    )


@dataclass
class Principal:
    user_id: str
    role: str  # 'admin' | 'user' | ...
    role_template_id: str
    tenant_id: str  # organization scope (v5.0: ORG_ID); not per-user isolation
    is_admin: bool
    api_key: str


def resolve_authenticated_principal(
    api_key: Optional[str],
    role_header: Optional[str],
    tenant_header: Optional[str],
    user_store: Any,
    *,
    authorization: Optional[str] = None,
    auth_token_store: Any = None,
) -> Principal:
    """Single source of truth for who-is-the-caller.

    Raises HTTPException(401/403/503) on failure. Caller-friendly: errors
    carry a ``detail`` string that is safe to surface to the client.
    """
    bearer = _bearer_token(authorization)
    if bearer is not None:
        return _principal_from_jwt(bearer, role_header, user_store, auth_token_store)

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing authentication")

    return _principal_from_api_key(api_key, role_header, user_store)


# Module-level store injection (mirrors existing init_xxx_api pattern).
_user_store: Any = None
_auth_token_store: Any = None


def init_auth(user_store: Any, auth_token_store: Any = None) -> None:
    """Wire stores on app startup. Called once from ``main.py``."""
    global _user_store, _auth_token_store
    _user_store = user_store
    _auth_token_store = auth_token_store


def get_user_store() -> Any:
    return _user_store


async def require_authenticated_user(
    *,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_user_role: Optional[str] = Header(default=None, alias="X-User-Role"),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
) -> Principal:
    return resolve_authenticated_principal(
        x_api_key,
        x_user_role,
        x_tenant_id,
        _user_store,
        authorization=authorization,
        auth_token_store=_auth_token_store,
    )


async def require_admin(
    principal: Principal = Depends(require_authenticated_user),
) -> Principal:
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    return principal


def require_module(module_name: str):
    """Factory: dependency that checks the user can access the given module.

    Replaces the previous per-router ``_check_xxx_module`` helpers that
    silently swallowed exceptions and returned ``None`` (effectively letting
    unauthenticated requests through). This version always raises on failure.
    """
    async def _dep(
        principal: Principal = Depends(require_authenticated_user),
    ) -> Principal:
        # Lazy import to avoid circular imports at module load time.
        from ..modules.registry import module_registry

        if not module_registry.is_enabled(module_name):
            raise HTTPException(
                status_code=503, detail=f"Module {module_name} disabled"
            )
        for dep in module_registry.get_requires(module_name):
            if not module_registry.is_enabled(dep):
                raise HTTPException(
                    status_code=503,
                    detail=f"Module {module_name} requires {dep}",
                )

        if principal.is_admin:
            return principal

        try:
            from ..gateway.role_template import role_template_manager
            if role_template_manager and not role_template_manager.can_access_module(
                principal.role_template_id, module_name
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Role cannot access module {module_name}",
                )
        except HTTPException:
            raise
        except Exception as e:
            # Initialization race: refuse with 503 instead of silently
            # admitting the request (previous code returned None here).
            raise HTTPException(
                status_code=503, detail=f"auth subsystem error: {e!r}"
            )
        return principal

    return _dep
