"""v5.0 scope helpers — org pool vs per-user BI/Insight/plan keys."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from ..org import ORG_ID
from ._auth import Principal


def org_scope(_: Principal) -> str:
    """Organization id for memories, knowledge, sessions."""
    return ORG_ID


def datasource_scope_id(
    principal: Principal,
    *,
    user_id: Optional[str] = None,
) -> str:
    """Per-user isolation key stored in legacy ``tenant_id`` columns (BI/Insight/plans).

    Non-admin callers always receive ``principal.user_id``. Admins may pass
    ``user_id`` (query param) to operate on another user's datasources.
    """
    override = (user_id or "").strip()
    if override:
        if not principal.is_admin:
            raise HTTPException(status_code=403, detail="无权访问其他用户数据源")
        return override
    return principal.user_id
