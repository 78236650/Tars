"""InsightForge workflow state hub (INS-2.0)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..database.base import Database, get_local_now
from ..database.bi_store import DataSource, DataSourceStore
from .config import get_insight_config
from .store import InsightMetricStore, InsightProfileRunStore
from .version import INS_VERSION
from .workflow_context import build_insight_workflow_context


STRIP_DATASOURCE_STATES = frozenset({"needs_forge", "forging", "forge_failed"})


def show_workflow_strip(datasource_state: str, session_state: str) -> bool:
    if datasource_state in STRIP_DATASOURCE_STATES:
        return True
    return session_state == "no_source"


class InsightWorkflowService:
    def __init__(
        self,
        db: Database,
        ds_store: Optional[DataSourceStore] = None,
        run_store: Optional[InsightProfileRunStore] = None,
        metric_store: Optional[InsightMetricStore] = None,
    ):
        self.db = db
        self.ds_store = ds_store or DataSourceStore(db)
        self.run_store = run_store or InsightProfileRunStore(db)
        self.metric_store = metric_store or InsightMetricStore(db)
        self.config = get_insight_config()

    def _workflow_from_ds(self, ds: DataSource) -> Dict[str, Any]:
        insight = (ds.schema_snapshot or {}).get("insight") or {}
        return dict(insight.get("workflow") or {})

    def get_datasource_state(self, datasource_id: str, tenant_id: str) -> str:
        ds = self.ds_store.get(datasource_id, tenant_id)
        if not ds:
            return "needs_forge"
        wf = self._workflow_from_ds(ds)
        return str(wf.get("state") or "needs_forge")

    def set_datasource_state(
        self,
        datasource_id: str,
        tenant_id: str,
        state: str,
        **extra: Any,
    ) -> None:
        ds = self.ds_store.get(datasource_id, tenant_id)
        if not ds:
            return
        snapshot = dict(ds.schema_snapshot or {})
        insight = dict(snapshot.get("insight") or {})
        workflow = dict(insight.get("workflow") or {})
        workflow["state"] = state
        workflow["ins_version"] = INS_VERSION
        for key, value in extra.items():
            if value is not None:
                workflow[key] = value
        if state == "ready":
            workflow["ready_at"] = get_local_now().isoformat()
        insight["workflow"] = workflow
        snapshot["insight"] = insight
        self.ds_store.update(datasource_id, tenant_id, schema_snapshot=snapshot)

    def get_session_insight(self, session_id: str, tenant_id: str) -> Dict[str, Any]:
        meta = self.db.get_session_metadata(session_id, tenant_id)
        return dict(meta.get("insight") or {})

    def patch_session_insight(
        self, session_id: str, tenant_id: str, patch: Dict[str, Any]
    ) -> Dict[str, Any]:
        meta = self.db.get_session_metadata(session_id, tenant_id)
        insight = dict(meta.get("insight") or {})
        insight.update(patch)
        meta["insight"] = insight
        self.db.set_session_metadata(session_id, tenant_id, meta)
        return insight

    def get_session_state(
        self, session_id: Optional[str], tenant_id: str, datasource_id: str
    ) -> str:
        if not session_id:
            return "idle"
        insight = self.get_session_insight(session_id, tenant_id)
        bound = insight.get("datasource_id")
        if not bound:
            return "no_source"
        if bound != datasource_id:
            return "no_source"
        return str(insight.get("state") or "idle")

    def bind_session_datasource(
        self, session_id: str, tenant_id: str, datasource_id: str
    ) -> None:
        self.patch_session_insight(
            session_id,
            tenant_id,
            {"datasource_id": datasource_id, "state": "idle"},
        )

    def set_session_asking_for_stream(self, session_id: str, tenant_id: str, asking: bool) -> None:
        self.patch_session_insight(
            session_id,
            tenant_id,
            {"state": "asking" if asking else "idle"},
        )

    def _forge_progress(self, datasource_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        runs = self.run_store.list_by_datasource(datasource_id, tenant_id, limit=1)
        if not runs:
            return None
        run = runs[0]
        if run.status not in ("pending", "running"):
            return None
        progress = run.progress_json or {}
        total = progress.get("total") or 0
        current = progress.get("current") or 0
        percent = int((current / total) * 100) if total else 0
        return {
            "phase": progress.get("phase"),
            "percent": percent,
            "message": progress.get("message"),
            "run_id": run.id,
        }

    def _block_reason(self, ds: DataSource, datasource_state: str) -> Optional[str]:
        if datasource_state == "forge_failed":
            wf = self._workflow_from_ds(ds)
            if wf.get("error"):
                return str(wf["error"])[:500]
            runs = self.run_store.list_by_datasource(ds.id, ds.tenant_id, limit=1)
            if runs and runs[0].error:
                return str(runs[0].error)[:500]
            return "鉴数失败，请重试"
        return None

    def _metric_counts(self, datasource_id: str, tenant_id: str) -> tuple[int, int]:
        metrics = self.metric_store.list_by_datasource(datasource_id, tenant_id)
        approved = sum(1 for m in metrics if m.status == "approved")
        draft = sum(1 for m in metrics if m.status == "draft")
        return approved, draft

    def get_composite(
        self,
        datasource_id: str,
        tenant_id: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        ds = self.ds_store.get(datasource_id, tenant_id)
        if not ds:
            raise ValueError("datasource not found")

        datasource_state = self.get_datasource_state(datasource_id, tenant_id)
        session_state = self.get_session_state(session_id, tenant_id, datasource_id)
        strip = show_workflow_strip(datasource_state, session_state)
        forge_progress = (
            self._forge_progress(datasource_id, tenant_id)
            if datasource_state == "forging"
            else None
        )
        block_reason = self._block_reason(ds, datasource_state)

        wf = self._workflow_from_ds(ds)
        insight_session = (
            self.get_session_insight(session_id, tenant_id) if session_id else {}
        )

        return {
            "datasource_state": datasource_state,
            "session_state": session_state,
            "show_workflow_strip": strip,
            "block_reason": block_reason,
            "forge_progress": forge_progress,
            "datasource_id": datasource_id,
            "datasource_name": ds.name,
            "pending_question": wf.get("pending_question"),
            "session_insight": insight_session,
            "ready_at": wf.get("ready_at"),
        }

    def get_llm_context_bundle(
        self,
        datasource_id: str,
        tenant_id: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        composite = self.get_composite(datasource_id, tenant_id, session_id)
        ds = self.ds_store.get(datasource_id, tenant_id)
        if not ds:
            return {}
        approved, draft = self._metric_counts(datasource_id, tenant_id)
        wf = self._workflow_from_ds(ds)
        return build_insight_workflow_context(
            datasource_state=composite["datasource_state"],
            session_state=composite["session_state"],
            show_workflow_strip=composite["show_workflow_strip"],
            datasource_id=datasource_id,
            datasource_name=ds.name,
            forge_progress=composite.get("forge_progress"),
            approved_metrics=approved,
            draft_metrics=draft,
            last_forge_at=wf.get("ready_at") or wf.get("last_forge_at"),
            block_reason=composite.get("block_reason"),
        )

    def transition_on_profile_start(self, datasource_id: str, tenant_id: str) -> None:
        self.set_datasource_state(datasource_id, tenant_id, "forging")

    def transition_on_profile_complete(
        self,
        datasource_id: str,
        tenant_id: str,
        *,
        error: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if error:
            self.set_datasource_state(
                datasource_id, tenant_id, "forge_failed", error=error
            )
            self._clear_pending_if_expired(datasource_id, tenant_id, failed=True)
            return None
        self.set_datasource_state(datasource_id, tenant_id, "ready")
        return self._consume_pending_question(datasource_id, tenant_id)

    def _clear_pending_if_expired(
        self, datasource_id: str, tenant_id: str, *, failed: bool = False
    ) -> None:
        ds = self.ds_store.get(datasource_id, tenant_id)
        if not ds:
            return
        snapshot = dict(ds.schema_snapshot or {})
        insight = dict(snapshot.get("insight") or {})
        workflow = dict(insight.get("workflow") or {})
        if failed or not workflow.get("pending_question"):
            workflow.pop("pending_question", None)
            insight["workflow"] = workflow
            snapshot["insight"] = insight
            self.ds_store.update(datasource_id, tenant_id, schema_snapshot=snapshot)

    def _consume_pending_question(
        self, datasource_id: str, tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        ds = self.ds_store.get(datasource_id, tenant_id)
        if not ds:
            return None
        snapshot = dict(ds.schema_snapshot or {})
        insight = dict(snapshot.get("insight") or {})
        workflow = dict(insight.get("workflow") or {})
        pending = workflow.get("pending_question")
        if not pending:
            return None

        ready_at = workflow.get("ready_at")
        ttl = self.config.forge.pending_question_ttl_seconds
        if ready_at and not self._pending_within_ttl(ready_at, ttl):
            workflow.pop("pending_question", None)
            insight["workflow"] = workflow
            snapshot["insight"] = insight
            self.ds_store.update(datasource_id, tenant_id, schema_snapshot=snapshot)
            return None

        workflow.pop("pending_question", None)
        insight["workflow"] = workflow
        snapshot["insight"] = insight
        self.ds_store.update(datasource_id, tenant_id, schema_snapshot=snapshot)
        return pending

    @staticmethod
    def _pending_within_ttl(ready_at: str, ttl_seconds: int) -> bool:
        try:
            ready_dt = datetime.fromisoformat(ready_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if ready_dt.tzinfo is None:
            ready_dt = ready_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - ready_dt.astimezone(timezone.utc)).total_seconds() <= ttl_seconds

    def set_pending_question(
        self,
        datasource_id: str,
        tenant_id: str,
        text: str,
        session_id: Optional[str] = None,
    ) -> None:
        pending = {"text": text, "session_id": session_id}
        self.set_datasource_state(
            datasource_id, tenant_id, self.get_datasource_state(datasource_id, tenant_id),
            pending_question=pending,
        )
