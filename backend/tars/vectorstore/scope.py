"""Org-scoped Chroma collection naming and memory visibility filters (TARS v5)."""
from typing import Any, Dict, Optional

from tars.org import ORG_ID


def collection_full_name(collection_name: str, tenant_id: str = "default") -> str:
    """Physical Chroma collection name (org-scoped; tenant_id kept for API compat)."""
    del tenant_id
    return f"{collection_name}_{ORG_ID}"


def memory_chroma_metadata(
    scope: str,
    user_id: Optional[str],
    **extra: Any,
) -> Dict[str, Any]:
    """Build Chroma metadata for a memory row (scope + user_id for visibility filters)."""
    meta = dict(extra)
    meta["scope"] = scope
    meta["user_id"] = user_id or ""
    return meta


def memory_visibility_filter(viewer_id: Optional[str] = None) -> Dict[str, Any]:
    """Chroma where clause matching memory_repo T2.1 visibility rules."""
    if viewer_id is None:
        return {"$or": [{"scope": "shared"}, {"user_id": ""}]}
    return {"$or": [{"scope": "shared"}, {"user_id": viewer_id}]}
