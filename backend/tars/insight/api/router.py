"""InsightForge API — /api/insight (INS-2.0.0)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ...api._auth import Principal, require_module
from ...database import Database
from ...database.bi_store import DataSourceStore
from ..config import get_insight_config
from ..job_runner import InsightJobRunner
from ..store import InsightMetricStore, InsightProfileRunStore
from ..version import CAPABILITY_NAME, CAPABILITY_TAG, INS_API_VERSION, INS_VERSION
from ..metric_qa_engine import InsightQaError, MetricQaEngine
from ..workflow_service import InsightWorkflowService

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

    from ..llm_resolver import init_llm_resolver
    init_llm_resolver(db)

    from ..agent_tools import init_insight_agent_tools
    from ...tools import registry as tool_registry

    for tool in init_insight_agent_tools(db):
        tool_registry.register(tool)

    # Recover any runs that were pending/running when the previous process died.
    # BackgroundTasks do not survive restarts, so leaving them stuck blocks future
    # runs and confuses the UI.
    try:
        swept = _run_store.sweep_stuck_runs()
        if swept:
            print(f"[Insight] sweep_stuck_runs marked {swept} run(s) as failed")
    except Exception as e:
        print(f"[Insight] sweep_stuck_runs failed: {e}")


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


class AskMetricRequest(BaseModel):
    question: str
    candidate_metric_keys: Optional[List[str]] = None
    as_of_date: Optional[str] = None
    session_id: Optional[str] = None


class InsightFeedbackBody(BaseModel):
    feedback: int


class AdoptMetricRequest(BaseModel):
    metric_id: Optional[str] = None
    definition: Optional[str] = None
    sql_template: Optional[str] = None
    question_log_id: Optional[str] = None


class StartProfileRequest(BaseModel):
    force: bool = False
    budget: Optional[Dict[str, Any]] = None
    llm: Optional[InsightLlmSelectionBody] = None
    pending_question: Optional[str] = None
    session_id: Optional[str] = None


def _workflow_service() -> InsightWorkflowService:
    if _db is None:
        raise HTTPException(status_code=500, detail="Insight API 未初始化")
    return InsightWorkflowService(_db, _ds_store, _run_store, _metric_store)


async def _start_forge_impl(
    datasource_id: str,
    body: StartProfileRequest,
    background_tasks: BackgroundTasks,
    principal: Principal,
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

    wf = _workflow_service()
    if body.pending_question:
        wf.set_pending_question(
            datasource_id,
            tenant_id,
            body.pending_question,
            session_id=body.session_id,
        )
    if body.session_id:
        wf.bind_session_datasource(body.session_id, tenant_id, datasource_id)

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
        "phase": {
            "workflow": True,
            "metric_qa_in_chat": True,
            "workbench": "ops_only",
            "chat_first_enabled": cfg.feature_flags.chat_first_enabled,
        },
    }


@router.get("/datasources/{datasource_id}/forge/events")
async def forge_events_sse(
    datasource_id: str,
    request: Request,
    principal: Principal = Depends(_require),
):
    """SSE stream for active forge run (in-process buffer; see deploy docs H1)."""
    from ..workflow_events import acquire_connection, aiter_sse

    if _run_store is None or _ds_store is None:
        raise HTTPException(status_code=500, detail="Insight API 未初始化")
    tenant_id = principal.tenant_id
    if not _ds_store.get(datasource_id, tenant_id):
        raise HTTPException(status_code=404, detail="数据源不存在")

    runs = _run_store.list_by_datasource(datasource_id, tenant_id, limit=1)
    if not runs or runs[0].status not in ("pending", "running"):
        raise HTTPException(status_code=404, detail="无进行中的鉴数任务")

    if not acquire_connection():
        raise HTTPException(
            status_code=429,
            detail={"code": "INSIGHT_SSE_RATE_LIMITED", "message": "SSE 连接数已满"},
        )

    last_id = 0
    header = request.headers.get("last-event-id")
    if header:
        try:
            last_id = int(header)
        except ValueError:
            last_id = 0

    run_id = runs[0].id

    async def event_stream():
        async for chunk in aiter_sse(run_id, last_id):
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/datasources/{datasource_id}/workflow")
async def get_datasource_workflow(
    datasource_id: str,
    session_id: Optional[str] = None,
    principal: Principal = Depends(_require),
):
    wf = _workflow_service()
    tenant_id = principal.tenant_id
    if _ds_store and not _ds_store.get(datasource_id, tenant_id):
        raise HTTPException(status_code=404, detail="数据源不存在")
    try:
        return wf.get_composite(datasource_id, tenant_id, session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="数据源不存在")


@router.post("/datasources/{datasource_id}/forge")
async def start_forge(
    datasource_id: str,
    body: StartProfileRequest,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(_require),
):
    """Canonical INS-2.0 endpoint to start profiling."""
    return await _start_forge_impl(
        datasource_id, body, background_tasks, principal
    )


@router.post("/datasources/{datasource_id}/profile")
async def start_profile(
    datasource_id: str,
    body: StartProfileRequest,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(_require),
):
    """INS-1.0 compatibility alias — forwards to /forge.

    Deprecated: prefer POST /datasources/{id}/forge (kept through INS-2.0 GA).
    """
    return await _start_forge_impl(
        datasource_id, body, background_tasks, principal
    )


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


@router.post("/datasources/{datasource_id}/ask")
async def ask_metric(
    datasource_id: str,
    body: AskMetricRequest,
    principal: Principal = Depends(_require),
):
    """Synchronous metric QA — does not set session asking (H2)."""
    if _db is None:
        raise HTTPException(status_code=500, detail="Insight API 未初始化")
    engine = MetricQaEngine(_db)
    try:
        answer = await engine.ask(
            datasource_id,
            principal.tenant_id,
            body.question,
            user_id=principal.user_id,
            candidate_metric_keys=body.candidate_metric_keys,
            as_of_date=body.as_of_date,
            session_id=body.session_id,
            is_second_partial_round=bool(body.candidate_metric_keys),
        )
    except InsightQaError as e:
        status = 400
        if e.code == "INSIGHT_NOT_PROFILED":
            status = 409
        elif e.code == "INSIGHT_WORKFLOW_BLOCKED":
            status = 409
        raise HTTPException(
            status_code=status,
            detail={"code": e.code, "message": e.message},
        )

    try:
        _db.add_audit_log(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            action="insight_ask",
            resource_type="datasource",
            resource_id=datasource_id,
            detail=json.dumps(
                {
                    "branch": answer.branch,
                    "caliber_tier": answer.caliber_tier,
                    "metric_key": answer.metric_key,
                    "question_log_id": answer.question_log_id,
                },
                ensure_ascii=False,
            ),
        )
    except Exception:
        pass

    return answer.to_dict()


@router.post("/datasources/{datasource_id}/ask/stream")
async def ask_metric_stream(
    datasource_id: str,
    body: AskMetricRequest,
    principal: Principal = Depends(_require),
):
    """Stream placeholder — sets session asking during execution (H2)."""
    wf = _workflow_service()
    if body.session_id:
        wf.set_session_asking_for_stream(body.session_id, principal.tenant_id, True)
    try:
        return await ask_metric(datasource_id, body, principal)
    finally:
        if body.session_id:
            wf.set_session_asking_for_stream(body.session_id, principal.tenant_id, False)


@router.post("/ask/{question_log_id}/feedback")
async def ask_feedback(
    question_log_id: str,
    body: InsightFeedbackBody,
    principal: Principal = Depends(_require),
):
    from ..question_log_store import InsightQuestionLogStore
    from ..adoption_service import AdoptionService

    if _db is None:
        raise HTTPException(status_code=500, detail="Insight API 未初始化")
    store = InsightQuestionLogStore(_db)
    ok = store.update_feedback(question_log_id, principal.tenant_id, body.feedback)
    if not ok:
        raise HTTPException(status_code=404, detail="问答记录不存在")
    adoption = AdoptionService(_db)
    result = adoption.process_feedback(
        question_log_id,
        principal.tenant_id,
        body.feedback,
        principal.user_id,
    )
    return result


def _adopt_metric_impl(
    metric_id: Optional[str],
    body: AdoptMetricRequest,
    principal: Principal,
):
    from ..adoption_service import AdoptionService
    from ..store import AdoptionConflictError

    if _db is None:
        raise HTTPException(status_code=500, detail="Insight API 未初始化")
    mid = (metric_id or body.metric_id or "").strip()
    service = AdoptionService(_db)
    try:
        result = service.adopt(
            mid,
            principal.tenant_id,
            principal.user_id,
            definition=body.definition,
            sql_template=body.sql_template,
            question_log_id=body.question_log_id,
        )
    except AdoptionConflictError:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INSIGHT_ADOPTION_CONFLICT",
                "message": "并发采用冲突，请重试",
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if result.get("code") == "INSIGHT_ADOPTION_PENDING_REVIEW":
        raise HTTPException(
            status_code=202,
            detail={
                "code": "INSIGHT_ADOPTION_PENDING_REVIEW",
                "message": "已提交待审",
                "adoption_id": result.get("adoption_id"),
            },
        )
    return {"success": True, **result}


@router.post("/metrics/adopt")
async def adopt_metric_body(
    body: AdoptMetricRequest,
    principal: Principal = Depends(_require),
):
    return _adopt_metric_impl(None, body, principal)


@router.post("/metrics/{metric_id}/adopt")
async def adopt_metric(
    metric_id: str,
    body: AdoptMetricRequest,
    principal: Principal = Depends(_require),
):
    return _adopt_metric_impl(metric_id, body, principal)


@router.get("/metrics/pending_adoption")
async def list_pending_adoption(principal: Principal = Depends(_require)):
    from ..adoption_service import AdoptionService

    if _db is None:
        raise HTTPException(status_code=500, detail="Insight API 未初始化")
    service = AdoptionService(_db)
    return {"items": service.list_pending_adoptions(principal.tenant_id)}


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
    cfg = get_insight_config()

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
            "metric_qa_in_chat": True,
            "workbench": "ops_only",
            "chat_first_enabled": cfg.feature_flags.chat_first_enabled,
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
