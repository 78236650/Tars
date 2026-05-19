"""InsightForge domain models (INS-1.0.0)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


PROFILE_STATUSES = ("pending", "running", "completed", "failed", "cancelled")
METRIC_STATUSES = ("draft", "approved", "deprecated")


@dataclass
class InsightProfileRun:
    id: str
    datasource_id: str
    tenant_id: str
    capability_version: str
    status: str
    budget_json: Dict[str, Any]
    progress_json: Dict[str, Any] = field(default_factory=dict)
    insight_snapshot_json: Optional[Dict[str, Any]] = None
    knowledge_doc_id: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class InsightMetric:
    id: str
    datasource_id: str
    tenant_id: str
    metric_key: str
    display_name: str
    definition: str
    sql_template: str = ""
    tables_json: List[str] = field(default_factory=list)
    status: str = "draft"
    source: str = "profile"
    confidence: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
