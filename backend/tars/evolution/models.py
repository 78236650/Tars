"""Evolution domain models (Phase 2)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class EvolutionEvent:
    tenant_id: str
    user_id: str
    source: str  # implicit | explicit | insight | curator
    signal: str
    payload: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    created_at: Optional[datetime] = None
    id: Optional[str] = None


@dataclass
class ApplyRecord:
    id: str
    tenant_id: str
    target_type: str
    target_path: str
    before_hash: str
    after_hash: str
    diff_summary: str = ""
    status: str = "applied"
