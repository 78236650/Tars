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
from .workflow_events import publish as publish_forge_event
from .workflow_service import InsightWorkflowService

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
        self.workflow = InsightWorkflowService(db)

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
            progress = {
                "phase": phase,
                "current": current,
                "total": total,
                "message": message,
            }
            self.run_store.update_progress(
                run_id,
                tenant_id,
                progress,
                status="running",
            )
            percent = int((current / total) * 100) if total else 0
            publish_forge_event(
                run_id,
                "progress",
                {
                    "run_id": run_id,
                    "phase": phase,
                    "percent": percent,
                    "message": message,
                },
            )

        self.run_store.update_progress(
            run_id,
            tenant_id,
            {"phase": "start", "current": 0, "total": 5, "message": "启动鉴数"},
            status="running",
        )
        self.workflow.transition_on_profile_start(datasource_id, tenant_id)
        publish_forge_event(
            run_id,
            "state_change",
            {"run_id": run_id, "from": "needs_forge", "to": "forging"},
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
            previous_run = self.run_store.latest_completed_for_datasource(
                datasource_id, tenant_id
            )
            previous_snapshot = None
            previous_completed_at = None
            if previous_run and previous_run.insight_snapshot_json:
                previous_snapshot = previous_run.insight_snapshot_json
                previous_completed_at = (
                    previous_run.finished_at
                    or previous_snapshot.get("completed_at")
                )

            force = bool((run.budget_json or {}).get("force"))

            result = await pipeline.run(
                ds,
                run_id=run_id,
                previous_snapshot=previous_snapshot,
                force=force,
                previous_completed_at=previous_completed_at,
            )
            if not result.get("success"):
                err = result.get("error", "profile failed")
                self.run_store.complete(
                    run_id,
                    tenant_id,
                    error=err,
                    status="failed",
                )
                self.workflow.transition_on_profile_complete(
                    datasource_id, tenant_id, error=str(err)
                )
                publish_forge_event(
                    run_id,
                    "failed",
                    {"run_id": run_id, "message": str(err), "retriable": True},
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

            metric_outcome = self.metric_store.replace_draft_metrics(
                datasource_id,
                tenant_id,
                result.get("metric_candidates") or [],
            )

            snapshot = result.get("insight_snapshot") or {}
            if llm_selection:
                snapshot["llm_used"] = llm_selection
            if metric_outcome.get("skipped"):
                snapshot.setdefault("llm_errors", []).append(
                    f"metric_keys_skipped_on_approved: {metric_outcome['skipped']}"
                )
            knowledge_doc_id = result.get("knowledge_doc_id")
            if _knowledge_indexer is not None and knowledge_doc_id is None:
                snapshot.setdefault("llm_errors", []).append("knowledge_publish_failed")

            self.run_store.complete(
                run_id,
                tenant_id,
                insight_snapshot=snapshot,
                knowledge_doc_id=knowledge_doc_id,
                status="completed",
            )
            pending = self.workflow.transition_on_profile_complete(
                datasource_id, tenant_id
            )
            if pending and pending.get("text"):
                await self._auto_ask_pending(
                    datasource_id,
                    tenant_id,
                    pending,
                )
            publish_forge_event(
                run_id,
                "completed",
                {
                    "run_id": run_id,
                    "doc_id": knowledge_doc_id,
                    "metrics_count": metric_outcome.get("inserted", 0),
                },
            )
            publish_forge_event(
                run_id,
                "state_change",
                {"run_id": run_id, "from": "forging", "to": "ready"},
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
            self.workflow.transition_on_profile_complete(
                datasource_id, tenant_id, error=str(e)
            )
            publish_forge_event(
                run_id,
                "failed",
                {"run_id": run_id, "message": str(e), "retriable": True},
            )

    async def _auto_ask_pending(
        self,
        datasource_id: str,
        tenant_id: str,
        pending: dict,
    ) -> None:
        """H5: after profile completes, run one ask for pending_question within TTL."""
        from .metric_qa_engine import MetricQaEngine

        question = (pending.get("text") or "").strip()
        if not question:
            return
        session_id = pending.get("session_id")
        engine = MetricQaEngine(self.db)
        try:
            await engine.ask(
                datasource_id,
                tenant_id,
                question,
                user_id="system",
                session_id=session_id,
            )
            logger.info(
                "[InsightForge/%s] auto-ask pending_question ds=%s",
                INS_VERSION,
                datasource_id,
            )
        except Exception as e:
            logger.warning(
                "[InsightForge] auto-ask pending_question failed: %s", e
            )
