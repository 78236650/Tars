"""InsightForge API — /api/insight (INS-1.0.0)."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from ...api._auth import Principal, require_module
from ...database import Database
from ...database.bi_store import DataSourceStore
from ..config import get_insight_config
from ..job_runner import InsightJobRunner
from ..store import InsightMetricStore, InsightProfileRunStore
from ..version import CAPABILITY_NAME, CAPABILITY_TAG, INS_API_VERSION, INS_VERSION

router = APIRouter(prefix="/api/insight", tags=["InsightForge"])


_db: Optional[Database] = None
_run_store: Optional[InsightProfileRunStore] = None
_metric_store: Optional[InsightMetricStore] = None
_ds_store: Optional[DataSourceStore] = None
_llm_settings_store = None


def init_insight_api(db: Database, knowledge_indexer=None) -> None:
    global _db, _run_store, _metric_store, _ds_store, _llm_settings_store
    _db = db
    _run_store = InsightProfileRunStore(db)
    _metric_store = InsightMetricStore(db)
    _ds_store = DataSourceStore(db)
    from ..llm_settings_store import InsightLlmSettingsStore

    _llm_settings_store = InsightLlmSettingsStore(db)
    from ..job_runner import set_insight_knowledge_indexer

    set_insight_knowledge_indexer(knowledge_indexer)


# All routes require an authenticated principal who can access the
# `insight` module. tenant_id is derived from the principal (admin can
# impersonate via X-Tenant-Id, non-admin always == user.id).
_require = require_module("insight")
router.dependencies = [Depends(_require)]


class InsightLlmSelectionBody(BaseModel):
    use_chat_default: bool = True
    provider: Optional[Literal["ollama", "openai_compatible"]] = None
    model: Optional[str] = None
    endpoint_id: Optional[str] = None
    persist: bool = False


class InsightLlmSettingsBody(BaseModel):
    use_chat_default: bool = True
    provider: Optional[Literal["ollama", "openai_compatible"]] = "ollama"
    model: Optional[str] = ""
    endpoint_id: Optional[str] = None


class StartProfileRequest(BaseModel):
    force: bool = False
    budget: Optional[Dict[str, Any]] = None
    llm: Optional[InsightLlmSelectionBody] = None


@router.get("/llm/options")
async def insight_llm_options(principal: Principal = Depends(_require)):
    """Same model catalog as Chat (Ollama + endpoints)."""
    from tars.models.config import get_models_root

    return await get_models_root()


@router.get("/llm/settings")
async def get_insight_llm_settings(
    principal: Principal = Depends(_require),
):
    if _llm_settings_store is None:
        raise HTTPException(status_code=500, detail="Insight API 未初始化")
    from ..llm_resolver import get_chat_model_selection, resolve_insight_llm

    saved = _llm_settings_store.get(principal.tenant_id)
    chat_current = get_chat_model_selection()
    effective = resolve_insight_llm(saved)
    return {
        "settings": saved.to_dict(),
        "chat_current": chat_current,
        "effective": {
            "label": effective.label,
            "source": effective.source,
            "selection": effective.selection,
        },
    }


@router.put("/llm/settings")
async def put_insight_llm_settings(
    body: InsightLlmSettingsBody,
    principal: Principal = Depends(_require),
):
    if _llm_settings_store is None:
        raise HTTPException(status_code=500, detail="Insight API 未初始化")
    from ..llm_settings_store import InsightLlmSettings
    from ..llm_resolver import get_chat_model_selection, resolve_insight_llm

    saved = _llm_settings_store.save(
        InsightLlmSettings(
            tenant_id=principal.tenant_id,
            use_chat_default=body.use_chat_default,
            provider=body.provider or "ollama",
            model=body.model or "",
            endpoint_id=body.endpoint_id,
        )
    )
    effective = resolve_insight_llm(saved)
    return {
        "success": True,
        "settings": saved.to_dict(),
        "chat_current": get_chat_model_selection(),
        "effective": {
            "label": effective.label,
            "source": effective.source,
            "selection": effective.selection,
        },
    }


@router.get("/version")
async def insight_version(principal: Principal = Depends(_require)):
    cfg = get_insight_config()
    return {
        "capability": CAPABILITY_NAME,
        "tag": CAPABILITY_TAG,
        "version": INS_VERSION,
        "api_version": INS_API_VERSION,
        "tier1_databases": cfg.tier1_databases,
        "tier2_databases": cfg.tier2_databases,
    }


@router.post("/datasources/{datasource_id}/profile")
async def start_profile(
    datasource_id: str,
    body: StartProfileRequest,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(_require),
):
    if _run_store is None or _ds_store is None or _db is None:
        raise HTTPException(status_code=500, detail="Insight API 未初始化")

    tenant_id = principal.tenant_id
    ds = _ds_store.get(datasource_id, tenant_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    cfg = get_insight_config()
    budget = dict(
        body.budget
        or {
            "max_tables": cfg.profile.max_tables,
            "sample_rows_per_table": cfg.profile.sample_rows_per_table,
            "force": body.force,
        }
    )
    budget["force"] = body.force

    if body.llm is not None:
        llm_payload = body.llm.model_dump(exclude={"persist"})
        budget["llm"] = llm_payload
        if body.llm.persist and _llm_settings_store is not None:
            from ..llm_settings_store import InsightLlmSettings

            _llm_settings_store.save(
                InsightLlmSettings(
                    tenant_id=tenant_id,
                    use_chat_default=body.llm.use_chat_default,
                    provider=body.llm.provider or "ollama",
                    model=body.llm.model or "",
                    endpoint_id=body.llm.endpoint_id,
                )
            )

    run = _run_store.create(
        datasource_id=datasource_id,
        tenant_id=tenant_id,
        capability_version=INS_VERSION,
        budget=budget,
    )

    runner = InsightJobRunner(_db)
    background_tasks.add_task(
        runner.start_profile, run.id, datasource_id, tenant_id
    )

    return {
        "success": True,
        "run_id": run.id,
        "status": run.status,
        "capability_version": INS_VERSION,
        "profile_mode": cfg.profile_mode_for_db(ds.db_type),
        "db_type": ds.db_type,
    }


@router.get("/datasources/{datasource_id}/profile/runs")
async def list_profile_runs(
    datasource_id: str,
    principal: Principal = Depends(_require),
):
    if _run_store is None:
        raise HTTPException(status_code=500, detail="Insight API 未初始化")
    runs = _run_store.list_by_datasource(datasource_id, principal.tenant_id)
    return {
        "runs": [
            {
                "id": r.id,
                "status": r.status,
                "capability_version": r.capability_version,
                "progress": r.progress_json,
                "error": r.error,
                "created_at": r.created_at,
                "finished_at": r.finished_at,
            }
            for r in runs
        ]
    }


@router.get("/profile/runs/{run_id}")
async def get_profile_run(
    run_id: str,
    principal: Principal = Depends(_require),
):
    if _run_store is None:
        raise HTTPException(status_code=500, detail="Insight API 未初始化")
    run = _run_store.get(run_id, principal.tenant_id)
    if not run:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "id": run.id,
        "datasource_id": run.datasource_id,
        "status": run.status,
        "capability_version": run.capability_version,
        "progress": run.progress_json,
        "insight_snapshot": run.insight_snapshot_json,
        "knowledge_doc_id": run.knowledge_doc_id,
        "error": run.error,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "created_at": run.created_at,
    }


@router.get("/datasources/{datasource_id}/brief")
async def get_datasource_brief(
    datasource_id: str,
    principal: Principal = Depends(_require),
):
    """工作台用：合并数据源、最新建档、标注与指标。"""
    if _run_store is None or _ds_store is None or _metric_store is None:
        raise HTTPException(status_code=500, detail="Insight API 未初始化")
    tenant_id = principal.tenant_id
    ds = _ds_store.get(datasource_id, tenant_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    runs = _run_store.list_by_datasource(datasource_id, tenant_id)
    latest = next((r for r in runs if r.status == "completed"), None) or (runs[0] if runs else None)
    annotations = ds.schema_annotations or {}
    tables = (ds.schema_snapshot or {}).get("tables") or {}
    metrics = _metric_store.list_by_datasource(datasource_id, tenant_id)
    snapshot = (latest.insight_snapshot_json if latest else None) or {}
    from ..snapshot_utils import split_snapshot_questions

    open_questions, llm_errors, llm_status = split_snapshot_questions(snapshot)

    return {
        "datasource": {
            "id": ds.id,
            "name": ds.name,
            "db_type": ds.db_type,
            "table_count": len(tables),
            "annotation_count": len(annotations),
        },
        "latest_run": (
            {
                "id": latest.id,
                "status": latest.status,
                "capability_version": latest.capability_version,
                "progress": latest.progress_json,
                "error": latest.error,
                "finished_at": latest.finished_at,
                "knowledge_doc_id": latest.knowledge_doc_id,
            }
            if latest
            else None
        ),
        "insight_snapshot": snapshot,
        "schema_annotations": annotations,
        "metrics": [
            {
                "id": m.id,
                "metric_key": m.metric_key,
                "display_name": m.display_name,
                "definition": m.definition,
                "status": m.status,
                "confidence": m.confidence,
            }
            for m in metrics
        ],
        "open_questions": open_questions,
        "llm_errors": llm_errors,
        "llm_status": llm_status,
        "llm_used": snapshot.get("llm_used"),
        "phase": {
            "profile": True,
            "metric_qa_in_chat": False,
            "workbench": True,
        },
    }


@router.get("/datasources/{datasource_id}/metrics")
async def list_metrics(
    datasource_id: str,
    principal: Principal = Depends(_require),
):
    if _metric_store is None:
        raise HTTPException(status_code=500, detail="Insight API 未初始化")
    metrics = _metric_store.list_by_datasource(datasource_id, principal.tenant_id)
    return {
        "metrics": [
            {
                "id": m.id,
                "metric_key": m.metric_key,
                "display_name": m.display_name,
                "definition": m.definition,
                "status": m.status,
                "confidence": m.confidence,
            }
            for m in metrics
        ]
    }
