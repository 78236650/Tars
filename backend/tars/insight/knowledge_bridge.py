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
        # v5.0.5/A8: 恢复被 cefa55c(删 knowledge 模块)误删的引用拼接。
        # 本函数是纯格式化,不依赖已移除的检索系统 —— 把指标定义的引用注脚
        # 拼回定义串,供 MetricAnswerCard 展示来源。
        if not citations:
            return definition or ""
        refs = " ".join(f"[ref:{c.doc_id}|{c.title}]" for c in citations[:3])
        base = (definition or "").strip()
        if refs in base:
            return base
        if base:
            return f"{base}\n\n参考：{refs}"
        return f"参考：{refs}"
