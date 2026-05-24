"""InsightForge ↔ knowledge base bridge (Phase 1 Data Copilot)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..knowledge.access import enrich_hit, search_knowledge
from .knowledge_publisher import KnowledgePublisher
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
    def __init__(self, db, retriever=None, indexer=None, settings: Optional[KnowledgeBridgeSettings] = None):
        self.db = db
        self.retriever = retriever
        self.indexer = indexer
        self.settings = settings or KnowledgeBridgeSettings()
        self._publisher = KnowledgePublisher(db, indexer)

    @staticmethod
    def collection_id_for(datasource_id: str) -> str:
        return f"insight_{datasource_id}"

    def retrieve_for_question(
        self,
        tenant_id: str,
        datasource_id: str,
        question: str,
        *,
        metric_key: Optional[str] = None,
    ) -> List[MetricCitation]:
        if not self.settings.enabled or not question.strip():
            return []
        if self.db is None:
            return []

        citations: List[MetricCitation] = []
        seen: set[str] = set()

        def add_from_hits(hits: List[Dict[str, Any]], source_type: str) -> None:
            nonlocal citations
            for hit in hits:
                enriched = enrich_hit(hit)
                citation_meta = enriched.get("citation") or {}
                doc_id = str(citation_meta.get("doc_id") or enriched.get("id") or "")
                if not doc_id or doc_id in seen:
                    continue
                seen.add(doc_id)
                title = str(citation_meta.get("doc_title") or "知识库文档")
                text = str(enriched.get("text") or "")
                snippet = text[: self.settings.max_snippet_chars]
                score = float(enriched.get("score") or 0.0)
                citations.append(
                    MetricCitation(
                        doc_id=doc_id,
                        title=title,
                        snippet=snippet,
                        source_type=source_type,
                        relevance=score,
                    )
                )
                if sum(len(c.snippet) for c in citations) >= self.settings.max_total_chars:
                    return

        insight_coll = self.collection_id_for(datasource_id)
        if self.retriever is not None:
            _, insight_hits = search_knowledge(
                self.db,
                self.retriever,
                question,
                tenant_id=tenant_id,
                collection_id=insight_coll,
                top_k=self.settings.insight_top_k,
            )
            add_from_hits(insight_hits, "insight_glossary")

            for prefix in self.settings.meeting_collection_prefixes:
                _, meeting_hits = search_knowledge(
                    self.db,
                    self.retriever,
                    question,
                    tenant_id=tenant_id,
                    collection_id=prefix,
                    top_k=self.settings.meeting_top_k,
                )
                add_from_hits(meeting_hits, "meeting_summary")

        if metric_key:
            linked = self._search_by_metric_id(tenant_id, metric_key)
            add_from_hits(linked, "metric_linked")

        return citations

    def _search_by_metric_id(self, tenant_id: str, metric_key: str) -> List[Dict[str, Any]]:
        from ..knowledge.sqlite_store import search_docs_by_metric_id

        try:
            return search_docs_by_metric_id(self.db, tenant_id, metric_key, top_k=5)
        except Exception:
            return []

    def publish_metric_card(
        self,
        datasource_id: str,
        datasource_name: str,
        tenant_id: str,
        metric: InsightMetric,
    ) -> Optional[str]:
        lines = [
            f"## 官方指标：{metric.metric_key}",
            "",
            f"- **metric_id**: `{metric.id}`",
            f"- **版本**: {metric.version}",
            "",
            metric.definition or "（无口径说明）",
            "",
            "### SQL 模板",
            "",
            "```sql",
            (metric.sql_template or "").strip(),
            "```",
        ]
        markdown = "\n".join(lines)
        doc_id = self._publisher.publish(
            datasource_id,
            datasource_name,
            tenant_id,
            markdown,
            run_id=metric.id,
            metric_ids=[metric.id],
        )
        return doc_id

    def enrich_definition(self, definition: str, citations: List[MetricCitation]) -> str:
        if not citations:
            return definition
        refs = " ".join(f"[ref:{c.doc_id}|{c.title}]" for c in citations[:3])
        base = (definition or "").strip()
        if refs in base:
            return base
        if base:
            return f"{base}\n\n参考：{refs}"
        return f"参考：{refs}"
