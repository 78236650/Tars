"""InsightForge ↔ Wiki bridge (knowledge module removed)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .metric_answer import MetricCitation
from .models import InsightMetric

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeBridgeSettings:
    enabled: bool = True
    timeout_ms: int = 500
    meeting_collection_prefixes: List[str] = field(default_factory=lambda: ["meeting"])
    max_snippet_chars: int = 200
    max_total_chars: int = 1500
    insight_top_k: int = 3
    meeting_top_k: int = 2


class KnowledgeBridge:
    def __init__(self, db, retriever=None, indexer=None, settings=None):
        self.db = db
        self.settings = settings or KnowledgeBridgeSettings()

    async def retrieve_for_question(self, tenant_id, datasource_id, question, *, metric_key=None):
        return []

    def publish_metric_card(self, datasource_id, datasource_name, tenant_id, metric):
        return None

    def enrich_definition(self, definition, citations):
        return definition or ""
