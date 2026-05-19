"""Metric QA routing and execution (INS-2.0)."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..bi.sql_agent import SQLAgent
from ..database.bi_store import DataSourceStore
from .config import InsightConfig, get_insight_config
from .metric_answer import MetricAnswer, MetricAnswerError
from .models import InsightMetric
from .question_log_store import InsightQuestionLogStore
from .store import InsightMetricStore
from .workflow_service import InsightWorkflowService

logger = logging.getLogger(__name__)

RouteFn = Callable[..., Awaitable[Dict[str, Any]]]
SqlExecutor = Callable[[str, str], Dict[str, Any]]


class InsightQaError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class RouteDecision:
    branch: str
    metric_key: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    open_questions: List[str] = None  # type: ignore

    def __post_init__(self):
        if self.open_questions is None:
            self.open_questions = []


class MetricQaEngine:
    def __init__(
        self,
        db,
        *,
        config: Optional[InsightConfig] = None,
        route_fn: Optional[RouteFn] = None,
        sql_executor: Optional[SqlExecutor] = None,
    ):
        self.db = db
        self.config = config or get_insight_config()
        self._sql_executor = sql_executor
        self.ds_store = DataSourceStore(db)
        self.metric_store = InsightMetricStore(db)
        self.question_log = InsightQuestionLogStore(db)
        self.workflow = InsightWorkflowService(db)
        self._route_fn = route_fn

    async def ask(
        self,
        datasource_id: str,
        tenant_id: str,
        question: str,
        *,
        user_id: str = "default",
        candidate_metric_keys: Optional[List[str]] = None,
        as_of_date: Optional[str] = None,
        session_id: Optional[str] = None,
        is_second_partial_round: bool = False,
    ) -> MetricAnswer:
        ds = self.ds_store.get(datasource_id, tenant_id)
        if not ds:
            raise InsightQaError("INSIGHT_DATASOURCE_NOT_FOUND", "数据源不存在")

        ds_state = self.workflow.get_datasource_state(datasource_id, tenant_id)
        if ds_state == "needs_forge":
            raise InsightQaError("INSIGHT_NOT_PROFILED", "请先完成鉴数")
        if ds_state in ("forging", "forge_failed"):
            raise InsightQaError("INSIGHT_WORKFLOW_BLOCKED", f"当前状态 {ds_state}，暂不可问数")

        if session_id:
            self.workflow.bind_session_datasource(session_id, tenant_id, datasource_id)

        metrics = self._candidate_metrics(
            datasource_id, tenant_id, candidate_metric_keys
        )
        fewshot = self.question_log.select_for_prompt(
            self.question_log.list_fewshot_candidates(datasource_id, tenant_id),
            max_items=self.config.qa.fewshot_max_items,
            max_tokens=self.config.qa.fewshot_max_tokens,
            recall_timeout_ms=self.config.qa.fewshot_recall_timeout_ms,
        )

        decision = await self._route(
            datasource_id=datasource_id,
            tenant_id=tenant_id,
            question=question,
            metrics=metrics,
            fewshot=fewshot,
            candidate_metric_keys=candidate_metric_keys,
        )

        if decision.branch == "hit_partial":
            if is_second_partial_round or candidate_metric_keys:
                if self.config.qa.allow_ad_hoc_sql:
                    decision = RouteDecision(branch="adhoc", confidence=0.5, reasoning="partial→adhoc")
                else:
                    return self._finish(
                        datasource_id,
                        tenant_id,
                        user_id,
                        question,
                        MetricAnswer(
                            value=None,
                            branch="rejected",
                            caliber_tier="adhoc",
                            definition="",
                            sql="",
                            filters_summary="",
                            confidence=decision.confidence,
                            open_questions=decision.open_questions,
                            candidates=self._partial_candidates(metrics, decision),
                            error=MetricAnswerError(
                                "INSIGHT_CLARIFY_FAILED", "无法澄清指标，已拒绝"
                            ),
                        ),
                    )
            return self._finish(
                datasource_id,
                tenant_id,
                user_id,
                question,
                MetricAnswer(
                    value=None,
                    branch="hit_partial",
                    caliber_tier="suggested",
                    definition="",
                    sql="",
                    filters_summary="",
                    confidence=decision.confidence,
                    reasoning=decision.reasoning,
                    open_questions=decision.open_questions
                    or ["请从候选指标中选择或补充说明"],
                    candidates=self._partial_candidates(metrics, decision),
                ),
            )

        if decision.branch == "miss" and not self.config.qa.allow_ad_hoc_sql:
            return self._finish(
                datasource_id,
                tenant_id,
                user_id,
                question,
                MetricAnswer(
                    value=None,
                    branch="rejected",
                    caliber_tier="adhoc",
                    definition="",
                    sql="",
                    filters_summary="",
                    confidence=decision.confidence,
                    reasoning=decision.reasoning,
                    error=MetricAnswerError("INSIGHT_ADHOC_DISABLED", "未命中指标且禁止 adhoc SQL"),
                ),
            )

        sql, metric, tier = await self._resolve_sql(
            datasource_id,
            tenant_id,
            ds.connection_url,
            question,
            decision,
            metrics,
            as_of_date,
            schema_snapshot=ds.schema_snapshot or {},
        )

        exec_result = self._run_sql(ds.connection_url, sql)

        if not exec_result.get("success"):
            return self._finish(
                datasource_id,
                tenant_id,
                user_id,
                question,
                MetricAnswer(
                    value=None,
                    branch=decision.branch,
                    caliber_tier=tier,
                    metric_key=metric.metric_key if metric else decision.metric_key,
                    definition=metric.definition if metric else "",
                    sql=exec_result.get("sql") or sql,
                    filters_summary="",
                    confidence=decision.confidence,
                    reasoning=decision.reasoning,
                    error=MetricAnswerError(
                        "INSIGHT_SQL_ERROR", exec_result.get("error") or "SQL 执行失败"
                    ),
                ),
                outcome="error",
            )

        value, unit = self._extract_scalar(exec_result.get("data") or [])
        as_of = as_of_date or date.today().isoformat()

        answer = MetricAnswer(
            value=value,
            unit=unit,
            caliber_tier=tier,
            metric_key=metric.metric_key if metric else decision.metric_key,
            metric_id=metric.id if metric else None,
            definition=(metric.definition if metric else decision.reasoning) or "",
            sql=exec_result.get("sql") or sql,
            filters_summary=self._filters_summary(question, as_of_date),
            as_of=as_of,
            lag_seconds=0,
            confidence=decision.confidence,
            branch=decision.branch,
            reasoning=decision.reasoning,
        )
        finished = self._finish(
            datasource_id,
            tenant_id,
            user_id,
            question,
            answer,
            outcome="success",
        )
        if session_id and finished.error is None:
            self.workflow.patch_session_insight(
                session_id,
                tenant_id,
                {
                    "insight_last": {
                        "sql": finished.sql,
                        "result": finished.value,
                        "metric_key": finished.metric_key,
                        "metric_id": finished.metric_id,
                        "question_log_id": finished.question_log_id,
                    },
                },
            )
        return finished

    def _run_sql(self, connection_url: str, sql: str) -> Dict[str, Any]:
        if self._sql_executor:
            return self._sql_executor(connection_url, sql)
        agent = SQLAgent(connection_url, max_retries=0)
        try:
            return agent.execute(sql)
        finally:
            agent.close()

    def _candidate_metrics(
        self,
        datasource_id: str,
        tenant_id: str,
        candidate_metric_keys: Optional[List[str]],
    ) -> List[InsightMetric]:
        if candidate_metric_keys:
            return self.metric_store.list_by_keys(
                datasource_id, tenant_id, candidate_metric_keys
            )
        return self.metric_store.list_by_datasource(datasource_id, tenant_id)

    def _partial_candidates(
        self, metrics: List[InsightMetric], decision: RouteDecision
    ) -> List[str]:
        if decision.metric_key:
            keys = [decision.metric_key]
        else:
            keys = [m.metric_key for m in metrics[:5]]
        return keys

    async def _route(
        self,
        *,
        datasource_id: str,
        tenant_id: str,
        question: str,
        metrics: List[InsightMetric],
        fewshot: List[Dict[str, Any]],
        candidate_metric_keys: Optional[List[str]],
    ) -> RouteDecision:
        if self._route_fn:
            raw = await self._route_fn(
                datasource_id=datasource_id,
                tenant_id=tenant_id,
                question=question,
                metrics=metrics,
                fewshot=fewshot,
                candidate_metric_keys=candidate_metric_keys,
            )
            return RouteDecision(
                branch=raw.get("branch", "miss"),
                metric_key=raw.get("metric_key"),
                confidence=float(raw.get("confidence") or 0),
                reasoning=str(raw.get("reasoning") or ""),
                open_questions=list(raw.get("open_questions") or []),
            )

        if candidate_metric_keys:
            for key in candidate_metric_keys:
                m = self.metric_store.get_by_key(datasource_id, tenant_id, key)
                if m:
                    return RouteDecision(
                        branch="hit_approved" if m.status == "approved" else "hit_draft",
                        metric_key=m.metric_key,
                        confidence=0.85,
                    )

        return self._heuristic_route(question, metrics)

    def _heuristic_route(self, question: str, metrics: List[InsightMetric]) -> RouteDecision:
        q = question.lower()
        approved = [m for m in metrics if m.status == "approved"]
        drafts = [m for m in metrics if m.status == "draft"]

        def score(m: InsightMetric) -> float:
            text = f"{m.metric_key} {m.display_name} {m.definition}".lower()
            hits = sum(1 for token in re.split(r"\W+", q) if token and token in text)
            return hits

        ranked = sorted(approved + drafts, key=score, reverse=True)
        if not ranked:
            return RouteDecision(branch="miss", confidence=0.0, reasoning="无可用指标")

        top = ranked[0]
        top_score = score(top)
        if top_score == 0:
            return RouteDecision(branch="miss", confidence=0.2, reasoning="未匹配到指标")

        ties = [m for m in ranked if score(m) == top_score]
        if len(ties) > 1:
            return RouteDecision(
                branch="hit_partial",
                confidence=0.5,
                reasoning="多个候选指标",
                open_questions=[f"请确认指标：{', '.join(m.metric_key for m in ties[:5])}"],
            )

        if top.status == "approved" and top_score >= 1:
            return RouteDecision(
                branch="hit_approved",
                metric_key=top.metric_key,
                confidence=min(0.95, 0.7 + 0.1 * top_score),
            )
        if top.status == "draft":
            return RouteDecision(
                branch="hit_draft",
                metric_key=top.metric_key,
                confidence=0.65,
            )
        return RouteDecision(branch="miss", confidence=0.3)

    async def _resolve_sql(
        self,
        datasource_id: str,
        tenant_id: str,
        connection_url: str,
        question: str,
        decision: RouteDecision,
        metrics: List[InsightMetric],
        as_of_date: Optional[str],
        *,
        schema_snapshot: Dict[str, Any],
    ) -> tuple[str, Optional[InsightMetric], str]:
        tier_map = {
            "hit_approved": "official",
            "hit_draft": "suggested",
            "adhoc": "adhoc",
        }
        tier = tier_map.get(decision.branch, "adhoc")

        if decision.branch in ("hit_approved", "hit_draft"):
            metric = next(
                (m for m in metrics if m.metric_key == decision.metric_key),
                None,
            )
            if not metric and decision.metric_key:
                metric = self.metric_store.get_by_key(
                    datasource_id, tenant_id, decision.metric_key
                )
            if not metric or not metric.sql_template.strip():
                raise InsightQaError("INSIGHT_METRIC_SQL_MISSING", "指标缺少 SQL 模板")
            sql = self._fill_sql_template(metric.sql_template, as_of_date)
            return sql, metric, tier

        tables = list((schema_snapshot.get("tables") or {}).keys())
        if tables:
            first_table = tables[0]
            sql = f"SELECT COUNT(*) AS value FROM {first_table}"
        else:
            sql = "SELECT 1 AS value"
        return sql, None, tier

    def _fill_sql_template(self, template: str, as_of_date: Optional[str]) -> str:
        as_of = as_of_date or (date.today() - timedelta(days=1)).isoformat()
        sql = template
        sql = sql.replace("{{as_of_date}}", as_of)
        sql = sql.replace("{{date}}", as_of)
        sql = sql.replace("{{yesterday}}", as_of)
        return sql.strip()

    def _extract_scalar(self, rows: List[Dict[str, Any]]) -> tuple[Any, Optional[str]]:
        if not rows:
            return None, None
        row = rows[0]
        if not row:
            return None, None
        if len(row) == 1:
            return next(iter(row.values())), None
        for key in ("value", "cnt", "count", "total", "gmv", "amount"):
            if key in row:
                return row[key], None
        return next(iter(row.values())), None

    def _filters_summary(self, question: str, as_of_date: Optional[str]) -> str:
        parts = [f"question={question[:120]}"]
        if as_of_date:
            parts.append(f"as_of={as_of_date}")
        return "; ".join(parts)

    def _finish(
        self,
        datasource_id: str,
        tenant_id: str,
        user_id: str,
        question: str,
        answer: MetricAnswer,
        *,
        outcome: str = "success",
    ) -> MetricAnswer:
        log_id = self.question_log.insert_log(
            datasource_id=datasource_id,
            tenant_id=tenant_id,
            question=question,
            sql=answer.sql or "--",
            branch=answer.branch,
            outcome=outcome if answer.error is None else "error",
            caliber_tier=answer.caliber_tier,
            user_id=user_id,
            metric_key=answer.metric_key,
        )
        answer.question_log_id = log_id
        return answer
