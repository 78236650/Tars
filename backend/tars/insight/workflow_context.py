"""LLM context bundle for InsightForge workflow (INS-2.0)."""
from __future__ import annotations

from typing import Any, Dict, Optional


def build_insight_workflow_context(
    *,
    datasource_state: str,
    session_state: str,
    show_workflow_strip: bool,
    datasource_id: str,
    datasource_name: str,
    forge_progress: Optional[Dict[str, Any]] = None,
    approved_metrics: int = 0,
    draft_metrics: int = 0,
    last_forge_at: Optional[str] = None,
    block_reason: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "insight_workflow": {
            "datasource_state": datasource_state,
            "session_state": session_state,
            "show_workflow_strip": show_workflow_strip,
            "datasource_id": datasource_id,
            "datasource_name": datasource_name,
            "forge_progress": forge_progress,
            "approved_metrics": approved_metrics,
            "draft_metrics": draft_metrics,
            "last_forge_at": last_forge_at,
            "block_reason": block_reason,
        }
    }
