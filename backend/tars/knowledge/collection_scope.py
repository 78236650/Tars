"""Knowledge collection tenant visibility (v5 org pool + legacy per-user rows)."""
from __future__ import annotations

from typing import List, Optional, Tuple

from tars.org import ORG_ID


def visible_kb_tenant_ids(user_id: Optional[str] = None) -> List[str]:
    """Tenant keys visible to the current user for KB list/read/write."""
    ids: List[str] = [ORG_ID]
    uid = (user_id or "").strip()
    if uid and uid not in ids:
        ids.append(uid)
    if "default" not in ids:
        ids.append("default")
    return ids


def tenant_in_sql(tenant_ids: List[str]) -> Tuple[str, Tuple[str, ...]]:
    placeholders = ",".join("?" * len(tenant_ids))
    return placeholders, tuple(tenant_ids)
