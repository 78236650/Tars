"""Async profile job runner."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..database.base import Database
from ..database.bi_store import DataSourceStore
from .config import get_insight_config
from .knowledge_publisher import KnowledgePublisher
from .profile_pipeline import ProfilePipeline
from .store import InsightMetricStore, InsightProfileRunStore
from .version import INS_VERSION

logger = logging.getLogger(__name__)

_knowledge_indexer = None


def set_insight_knowledge_indexer(indexer) -> None:
    global _knowledge_indexer
    _knowledge_indexer = indexer


class InsightJobRunner:
    """Orchestrates InsightForge profile runs."""

    def __init__(self, db: Database):
        self.db = db
        self.run_store = InsightProfileRunStore(db)
        self.metric_store = InsightMetricStore(db)
        self.ds_store = DataSourceStore(db)
        self.config = get_insight_config()

    async def start_profile(
        self,
        run_id: str,
        datasource_id: str,
        tenant_id: str = "default",
    ) -> None:
        run = self.run_store.get(run_id, tenant_id)
        if not run:
            logger.error("[InsightForge] run not found: %s", run_id)
            return

        ds = self.ds_store.get(datasource_id, tenant_id)
        if not ds:
            self.run_store.complete(
                run_id, tenant_id, error="数据源不存在", status="failed"
            )
            return

        def on_progress(phase: str, current: int, total: int, message: str):
            self.run_store.update_progress(
                run_id,
                tenant_id,
                {
                    "phase": phase,
                    "current": current,
                    "total": total,
                    "message": message,
                },
                status="running",
            )

        self.run_store.update_progress(
            run_id,
            tenant_id,
            {"phase": "start", "current": 0, "total": 5, "message": "启动鉴数"},
            status="running",
        )

        llm_override = (run.budget_json or {}).get("llm")
        llm_provider = None
        llm_selection = {}
        try:
            from .llm_settings_store import InsightLlmSettings, InsightLlmSettingsStore
            from .llm_resolver import resolve_insight_llm

            settings_store = InsightLlmSettingsStore(self.db)
            tenant_settings = settings_store.get(tenant_id)
            resolved = resolve_insight_llm(tenant_settings, override=llm_override)
            llm_provider = resolved.provider
            llm_selection = {
                **resolved.selection,
                "source": resolved.source,
            }
        except Exception as e:
            logger.warning("[InsightForge] LLM resolve failed, using default: %s", e)

        publisher = KnowledgePublisher(self.db, _knowledge_indexer)
        pipeline = ProfilePipeline(
            knowledge_publisher=publisher,
            on_progress=on_progress,
            llm_provider=llm_provider,
        )

        try:
            result = await pipeline.run(ds)
            if not result.get("success"):
                self.run_store.complete(
                    run_id,
                    tenant_id,
                    error=result.get("error", "profile failed"),
                    status="failed",
                )
                return

            from ..database.base import get_local_now

            merged_schema = result["schema_snapshot"]
            insight_block = merged_schema.get("insight") or {}
            insight_block["last_run_id"] = run_id
            insight_block["last_completed_at"] = get_local_now().isoformat()
            merged_schema["insight"] = insight_block

            self.ds_store.update(
                datasource_id,
                tenant_id,
                schema_snapshot=merged_schema,
                schema_annotations=result.get("schema_annotations") or {},
            )

            self.metric_store.replace_draft_metrics(
                datasource_id,
                tenant_id,
                result.get("metric_candidates") or [],
            )

            snapshot = result.get("insight_snapshot") or {}
            if llm_selection:
                snapshot["llm_used"] = llm_selection

            self.run_store.complete(
                run_id,
                tenant_id,
                insight_snapshot=snapshot,
                knowledge_doc_id=result.get("knowledge_doc_id"),
                status="completed",
            )
            logger.info(
                "[InsightForge/%s] profile completed ds=%s tables=%s",
                INS_VERSION,
                datasource_id,
                len((result.get("insight_snapshot") or {}).get("tables") or {}),
            )
        except Exception as e:
            logger.exception("[InsightForge] profile failed: %s", e)
            self.run_store.complete(
                run_id, tenant_id, error=str(e), status="failed"
            )
