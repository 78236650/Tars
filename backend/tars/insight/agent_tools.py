"""InsightForge Agent tools (INS-2.0 M4)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..database.base import Database
from ..database.bi_store import DataSourceStore
from ..tools.base import BaseTool, ToolResult
from .adoption_service import AdoptionService
from .job_runner import InsightJobRunner
from .metric_qa_engine import InsightQaError, MetricQaEngine
from .question_log_store import InsightQuestionLogStore
from .store import AdoptionConflictError, InsightMetricStore, InsightProfileRunStore
from .workflow_service import InsightWorkflowService

_db: Optional[Database] = None
_knowledge_bridge = None


def init_insight_agent_tools(db: Database, knowledge_bridge=None) -> List[BaseTool]:
    global _db, _knowledge_bridge
    _db = db
    _knowledge_bridge = knowledge_bridge
    return [
        InsightGetWorkflowTool(),
        InsightListSourcesTool(),
        InsightStartForgeTool(),
        InsightProfileDatasourceTool(),
        InsightAskMetricTool(),
        InsightAdoptMetricTool(),
        InsightExplainMetricTool(),
        InsightGiveFeedbackTool(),
    ]


def _require_db() -> Database:
    if _db is None:
        raise RuntimeError("Insight agent tools not initialized")
    return _db


class InsightGetWorkflowTool(BaseTool):
    name = "insight_get_workflow"
    description = "获取 InsightForge 鉴数工作流合成状态（数据源状态、会话状态、鉴数进度等）。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "datasource_id": {"type": "string", "description": "数据源 ID"},
            "session_id": {"type": "string", "description": "会话 ID（可选）"},
            "tenant_id": {"type": "string", "description": "租户 ID，默认 default"},
        },
        "required": ["datasource_id"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        db = _require_db()
        tenant_id = kwargs.get("tenant_id", "default")
        wf = InsightWorkflowService(db)
        try:
            composite = wf.get_composite(
                kwargs["datasource_id"], tenant_id, kwargs.get("session_id")
            )
            bundle = wf.get_llm_context_bundle(
                kwargs["datasource_id"], tenant_id, kwargs.get("session_id")
            )
            return ToolResult(
                success=True,
                output=json.dumps(bundle, ensure_ascii=False, indent=2),
                metadata={"workflow": composite},
            )
        except ValueError as e:
            return ToolResult(success=False, output="", error=str(e))


class InsightListSourcesTool(BaseTool):
    name = "insight_list_sources"
    description = "列出可问数的 InsightForge 数据源及工作流状态摘要。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "tenant_id": {"type": "string", "description": "租户 ID，默认 default"},
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        db = _require_db()
        tenant_id = kwargs.get("tenant_id", "default")
        bi = DataSourceStore(db)
        wf = InsightWorkflowService(db)
        lines = []
        items = []
        for ds in bi.list_by_tenant(tenant_id):
            state = wf.get_datasource_state(ds.id, tenant_id)
            lines.append(f"- {ds.name} ({ds.id}) state={state}")
            items.append({"id": ds.id, "name": ds.name, "state": state})
        return ToolResult(
            success=True,
            output="\n".join(lines) if lines else "暂无数据源",
            metadata={"sources": items},
        )


class _ForgeStartMixin:
    async def _start_forge(self, **kwargs) -> ToolResult:
        db = _require_db()
        tenant_id = kwargs.get("tenant_id", "default")
        ds_id = kwargs.get("datasource_id", "").strip()
        if not ds_id:
            return ToolResult(success=False, output="", error="需要 datasource_id")
        bi = DataSourceStore(db)
        if not bi.get(ds_id, tenant_id):
            return ToolResult(success=False, output="", error="数据源不存在")
        run_store = InsightProfileRunStore(db)
        from .config import get_insight_config
        from .version import INS_VERSION

        cfg = get_insight_config()
        run = run_store.create(ds_id, tenant_id, INS_VERSION, cfg.profile.__dict__)
        wf = InsightWorkflowService(db)
        wf.transition_on_profile_start(ds_id, tenant_id)
        pending_q = kwargs.get("pending_question")
        if pending_q:
            wf.set_pending_question(ds_id, tenant_id, pending_q, kwargs.get("session_id"))
        runner = InsightJobRunner(db)
        import asyncio

        loop = asyncio.get_running_loop()
        loop.create_task(runner.start_profile(run.id, ds_id, tenant_id))
        return ToolResult(
            success=True,
            output=f"已启动鉴数 run_id={run.id}",
            metadata={"run_id": run.id},
        )


class InsightStartForgeTool(_ForgeStartMixin, BaseTool):
    name = "insight_start_forge"
    description = "启动 InsightForge 鉴数（建档）任务。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "datasource_id": {"type": "string"},
            "pending_question": {"type": "string", "description": "鉴数完成后自动问数的问题"},
            "session_id": {"type": "string"},
            "tenant_id": {"type": "string"},
        },
        "required": ["datasource_id"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        return await self._start_forge(**kwargs)


class InsightProfileDatasourceTool(_ForgeStartMixin, BaseTool):
    name = "insight_profile_datasource"
    description = "与 insight_start_forge 相同，启动数据源鉴数建档（INS-1.0 兼容名）。"
    parameters_schema = InsightStartForgeTool.parameters_schema

    async def execute(self, **kwargs) -> ToolResult:
        return await self._start_forge(**kwargs)


class InsightAskMetricTool(BaseTool):
    name = "insight_ask_metric"
    description = "在已鉴数数据源上问数，返回 MetricAnswer（数值、口径、SQL）。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "datasource_id": {"type": "string"},
            "question": {"type": "string"},
            "session_id": {"type": "string"},
            "candidate_metric_keys": {"type": "array", "items": {"type": "string"}},
            "as_of_date": {"type": "string"},
            "tenant_id": {"type": "string"},
            "user_id": {"type": "string"},
        },
        "required": ["datasource_id", "question"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        db = _require_db()
        tenant_id = kwargs.get("tenant_id", "default")
        engine = MetricQaEngine(db)
        try:
            answer = await engine.ask(
                kwargs["datasource_id"],
                tenant_id,
                kwargs["question"],
                user_id=kwargs.get("user_id", "default"),
                candidate_metric_keys=kwargs.get("candidate_metric_keys"),
                as_of_date=kwargs.get("as_of_date"),
                session_id=kwargs.get("session_id"),
            )
        except InsightQaError as e:
            return ToolResult(success=False, output="", error=f"{e.code}: {e.message}")
        data = answer.to_dict()
        return ToolResult(
            success=answer.error is None,
            output=json.dumps(data, ensure_ascii=False, default=str),
            metadata=data,
        )


class InsightAdoptMetricTool(BaseTool):
    name = "insight_adopt_metric"
    description = "将采用口径晋升为官方 approved 指标。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "metric_id": {"type": "string"},
            "question_log_id": {"type": "string", "description": "无 metric_id 时从问答记录创建 draft"},
            "definition": {"type": "string"},
            "sql_template": {"type": "string"},
            "tenant_id": {"type": "string"},
            "user_id": {"type": "string"},
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        import asyncio

        db = _require_db()
        metric_id = kwargs.get("metric_id", "").strip()
        log_id = kwargs.get("question_log_id")
        if not metric_id and not log_id:
            return ToolResult(success=False, output="", error="需要 metric_id 或 question_log_id")
        from ..config import get_insight_config

        cfg = get_insight_config()
        service = AdoptionService(db, config=cfg, knowledge_bridge=_knowledge_bridge)
        tenant_id = kwargs.get("tenant_id", "default")
        user_id = kwargs.get("user_id", "default")
        defer_publish = bool(_knowledge_bridge and cfg.adoption.publish_to_knowledge)
        try:
            result = service.adopt(
                metric_id,
                tenant_id,
                user_id,
                definition=kwargs.get("definition"),
                sql_template=kwargs.get("sql_template"),
                question_log_id=log_id,
                defer_publish=defer_publish,
            )
        except AdoptionConflictError:
            return ToolResult(
                success=False,
                output="",
                error="INSIGHT_ADOPTION_CONFLICT: 并发采用冲突",
            )
        except ValueError as e:
            return ToolResult(success=False, output="", error=str(e))
        if defer_publish and result.get("metric"):
            approved = InsightMetricStore(db).get_by_id(result["metric"]["id"], tenant_id)
            if approved:
                asyncio.create_task(
                    asyncio.to_thread(
                        service.publish_adopted_metric,
                        approved,
                        tenant_id,
                        user_id,
                    )
                )
        if result.get("status") == "pending_review":
            return ToolResult(
                success=True,
                output="已提交待审",
                metadata=result,
            )
        return ToolResult(
            success=True,
            output=json.dumps(result.get("metric"), ensure_ascii=False),
            metadata=result,
        )


class InsightExplainMetricTool(BaseTool):
    name = "insight_explain_metric"
    description = "解释指标口径与 SQL 模板，不执行查询。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "datasource_id": {"type": "string"},
            "metric_key": {"type": "string"},
            "tenant_id": {"type": "string"},
        },
        "required": ["datasource_id", "metric_key"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        db = _require_db()
        tenant_id = kwargs.get("tenant_id", "default")
        store = InsightMetricStore(db)
        m = store.get_current_by_key(
            kwargs["datasource_id"], tenant_id, kwargs["metric_key"]
        )
        if not m:
            return ToolResult(success=False, output="", error="指标不存在")
        text = (
            f"指标: {m.display_name} ({m.metric_key})\n"
            f"状态: {m.status} v{m.version}\n"
            f"口径: {m.definition}\n"
            f"SQL 模板:\n{m.sql_template}"
        )
        return ToolResult(success=True, output=text, metadata={"metric": m.metric_key})


class InsightGiveFeedbackTool(BaseTool):
    name = "insight_give_feedback"
    description = "对问数记录提交 👍(1) 或 👎(-1) 反馈。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "question_log_id": {"type": "string"},
            "feedback": {"type": "integer", "description": "1 或 -1"},
            "tenant_id": {"type": "string"},
            "user_id": {"type": "string"},
        },
        "required": ["question_log_id", "feedback"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        db = _require_db()
        tenant_id = kwargs.get("tenant_id", "default")
        log_id = kwargs["question_log_id"]
        score = int(kwargs["feedback"])
        store = InsightQuestionLogStore(db)
        if not store.update_feedback(log_id, tenant_id, score):
            return ToolResult(success=False, output="", error="问答记录不存在")
        adoption = AdoptionService(db)
        result = adoption.process_feedback(
            log_id, tenant_id, score, kwargs.get("user_id", "default")
        )
        return ToolResult(success=True, output=json.dumps(result), metadata=result)
