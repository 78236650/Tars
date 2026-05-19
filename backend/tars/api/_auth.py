"""Centralized authentication dependency for all FastAPI routers.

Replaces the per-route ``except Exception: return`` anti-pattern with a single
source of truth for principal resolution. All routes that previously read
``X-API-Key`` / ``X-User-Role`` / ``X-Tenant-Id`` headers should depend on
``require_authenticated_user`` (or ``require_admin`` / ``require_module(name)``)
instead.

Auth model:

- ``X-API-Key`` is **required**. Missing or unknown -> 401.
- ``X-User-Role: admin`` is a client-controlled hint. It is honoured **only**
  when the api key resolves to a user whose ``role`` is ``admin``. A non-admin
  user sending the header is rejected with 403.
- ``X-Tenant-Id`` is honoured for impersonation **only** when the resolved
  user is admin. Non-admin requests have ``tenant_id`` derived from
  ``user.id`` (TARS data model: user_id == tenant_id).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException


@dataclass
class Principal:
    user_id: str
    role: str  # 'admin' | 'user' | ...
    role_template_id: str
    tenant_id: str  # already derived: admin+header -> header value, else user_id
    is_admin: bool
    api_key: str


def resolve_authenticated_principal(
    api_key: Optional[str],
    role_header: Optional[str],
    tenant_header: Optional[str],
    user_store: Any,
) -> Principal:
    """Single source of truth for who-is-the-caller.

    Raises HTTPException(401/403/503) on failure. Caller-friendly: errors
    carry a ``detail`` string that is safe to surface to the client.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key")
    if user_store is None:
        # Auth subsystem not initialized yet — refuse rather than silently
        # falling through (the previous pattern was ``except: return``).
        raise HTTPException(status_code=503, detail="auth subsystem not initialized")

    user = user_store.get_user_by_api_key(api_key)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    is_admin = (getattr(user, "role", None) == "admin")

    # X-User-Role: admin is client-controlled; only honour it for real admins.
    if role_header == "admin" and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="X-User-Role admin requires admin api key",
        )

    # tenant derivation: non-admin always uses user.id; admin can impersonate
    # via X-Tenant-Id header (used for cross-tenant ops in the admin UI).
    if is_admin and tenant_header:
        tenant_id = tenant_header
    else:
        tenant_id = user.id  # TARS data model: user_id == tenant_id

    return Principal(
        user_id=user.id,
        role=getattr(user, "role", "user"),
        role_template_id=getattr(user, "role_template_id", None) or "standard",
        tenant_id=tenant_id,
        is_admin=is_admin,
        api_key=api_key,
    )


# Module-level user_store injection (mirrors existing init_xxx_api pattern).
_user_store: Any = None


def init_auth(user_store: Any) -> None:
    """Wire the user store on app startup. Called once from ``main.py``."""
    global _user_store
    _user_store = user_store


def get_user_store() -> Any:
    return _user_store


async def require_authenticated_user(
    *,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_user_role: Optional[str] = Header(default=None, alias="X-User-Role"),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
) -> Principal:
    return resolve_authenticated_principal(
        x_api_key, x_user_role, x_tenant_id, _user_store
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
