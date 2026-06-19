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
from .metric_answer import MetricAnswer, MetricAnswerError, MetricCitation
from .models import InsightMetric
from .question_log_store import InsightQuestionLogStore
from .sql_quoting import apply_tables_quoting
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
        llm_provider=None,
        knowledge_bridge=None,
        glossary_lookup=None,
    ):
        self.db = db
        self.config = config or get_insight_config()
        self._sql_executor = sql_executor
        self._llm_provider = llm_provider
        self.ds_store = DataSourceStore(db)
        self.metric_store = InsightMetricStore(db)
        self.question_log = InsightQuestionLogStore(db)
        self.workflow = InsightWorkflowService(db)
        self._route_fn = route_fn
        self._knowledge_bridge = knowledge_bridge
        self._glossary_lookup = glossary_lookup

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

        if decision.branch in ("adhoc", "miss"):
            # v5.3.0: 启用 adhoc NL→SQL（需 LLM provider 可用）
            if not self.config.qa.allow_ad_hoc_sql or self._llm_provider is None:
                return self._finish(
                    datasource_id,
                    tenant_id,
                    user_id,
                    question,
                    MetricAnswer(
                        value=None,
                        branch=decision.branch,
                        caliber_tier="adhoc",
                        definition="",
                        sql="",
                        filters_summary=self._filters_summary(question, as_of_date),
                        confidence=decision.confidence,
                        reasoning=decision.reasoning,
                        open_questions=decision.open_questions
                        or ["请从已鉴数指标中选择，或补充 metric_key 后重试"],
                        error=MetricAnswerError(
                            "INSIGHT_ADHOC_SQL_NOT_AVAILABLE",
                            "未命中可执行口径，暂不支持自动生成 SQL",
                        ),
                    ),
                    outcome="error",
                )
            # fall through to _resolve_sql for adhoc generation

        sql, metric, tier = await self._resolve_sql(
            datasource_id,
            tenant_id,
            ds.connection_url,
            ds.db_type,
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
        answer = await self._apply_knowledge_citations(
            answer,
            tenant_id=tenant_id,
            datasource_id=datasource_id,
            question=question,
            metric_key=answer.metric_key,
        )
        answer = self._apply_glossary(answer, question=question)
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
        db_type: str,
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
            sql = apply_tables_quoting(sql, metric.tables_json, db_type)
            return sql, metric, tier

        # v5.3.0: adhoc NL→SQL 生成
        if self._llm_provider is None:
            raise InsightQaError(
                "INSIGHT_ADHOC_SQL_NOT_AVAILABLE",
                "未命中可执行口径，且无可用 LLM 生成 SQL",
            )
        sql = await self._build_adhoc_sql(
            question=question,
            schema_snapshot=schema_snapshot,
            db_type=db_type,
            as_of_date=as_of_date,
        )
        return sql, None, tier

    def _fill_sql_template(self, template: str, as_of_date: Optional[str]) -> str:
        as_of = as_of_date or (date.today() - timedelta(days=1)).isoformat()
        sql = template
        sql = sql.replace("{{as_of_date}}", as_of)
        sql = sql.replace("{{date}}", as_of)
        sql = sql.replace("{{yesterday}}", as_of)
        return sql.strip()

    async def _build_adhoc_sql(
        self,
        *,
        question: str,
        schema_snapshot: Dict[str, Any],
        db_type: str,
        as_of_date: Optional[str] = None,
    ) -> str:
        """v5.3.0: 用 LLM 从自然语言问题 + Schema 上下文生成 SQL。

        仅用于 adhoc/miss 分支，不涉及预定义指标模板。
        """
        if self._llm_provider is None:
            raise InsightQaError("INSIGHT_ADHOC_NO_LLM", "无可用 LLM 生成 adhoc SQL")

        tables = schema_snapshot.get("tables") or {}
        if not tables:
            raise InsightQaError("INSIGHT_NO_SCHEMA", "数据源缺少 Schema 信息，请先完成鉴数")

        # 构建精简 Schema 描述（限制 token 消耗）
        schema_lines: list[str] = []
        for tname, tdef in tables.items():
            cols = tdef.get("columns") or []
            if not cols:
                continue
            col_strs = []
            for c in cols[:30]:  # 每表最多 30 列
                cname = c.get("name", "?")
                ctype = c.get("type", "text")
                comment = c.get("comment") or ""
                col_strs.append(f"  {cname} {ctype}" + (f" -- {comment}" if comment else ""))
            pk = tdef.get("primary_key") or []
            pk_str = f" PK=({', '.join(pk)})" if pk else ""
            schema_lines.append(f"CREATE TABLE {tname} ({chr(10)}{chr(10).join(col_strs)}{chr(10)}){pk_str};")

        schema_text = "\n\n".join(schema_lines[:20])  # 最多 20 张表
        as_of = as_of_date or (date.today() - timedelta(days=1)).isoformat()

        prompt = f"""你是一个 {db_type.upper()} SQL 专家。根据以下 DDL 和业务问题，生成一条**只读 SELECT** 查询。

数据库方言：{db_type.upper()}
数据日期参考：{as_of}（如问"昨天"用此日期）

DDL:
{schema_text}

问题：{question}

要求：
- 只输出 SQL，不要任何解释或 markdown 包裹
- 仅使用 SELECT/WITH 语句
- 查询结果尽量简洁（聚合到少数行）
- 日期过滤优先用 {as_of} 或合理推算
- 如不确定，输出你能确定的最合理 SQL"""

        try:
            response = await self._llm_provider.complete(prompt, max_tokens=800)
            content = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            raise InsightQaError("INSIGHT_LLM_FAILED", f"LLM 调用失败: {e}")

        sql = self._extract_sql(content)
        if not sql:
            raise InsightQaError("INSIGHT_SQL_PARSE_FAILED", "LLM 返回的 SQL 无法解析")

        # 引用校正（与 hit 分支一致）
        sql = apply_tables_quoting(sql, "[]", db_type)
        logger.info("[InsightForge adhoc] generated SQL: %s", sql[:200])
        return sql

    @staticmethod
    def _extract_sql(text: str) -> str:
        """从 LLM 响应中提取纯 SQL 文本。"""
        t = text.strip()
        # 去 markdown 包裹
        if t.startswith("```"):
            t = re.sub(r"^```(?:sql)?\s*", "", t)
            t = re.sub(r"\s*```$", "", t)
        # 找 SELECT 开头
        m = re.search(r"(?i)\b(SELECT|WITH)\b[\s\S]*", t)
        if m:
            return m.group(0).strip().rstrip(";")
        return t.strip().rstrip(";")

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

    async def _apply_knowledge_citations(
        self,
        answer: MetricAnswer,
        *,
        tenant_id: str,
        datasource_id: str,
        question: str,
        metric_key: Optional[str] = None,
    ) -> MetricAnswer:
        if not self._knowledge_bridge:
            return answer
        try:
            citations = await self._knowledge_bridge.retrieve_for_question(
                tenant_id,
                datasource_id,
                question,
                metric_key=metric_key,
            )
        except Exception as exc:
            logger.warning("KnowledgeBridge retrieve failed: %s", exc)
            return answer
        answer.citations = citations
        if citations and self.config.qa.require_metric_citation:
            answer.definition = self._knowledge_bridge.enrich_definition(
                answer.definition, citations
            )
        return answer

    def _apply_glossary(self, answer: MetricAnswer, *, question: str) -> MetricAnswer:
        if not self._glossary_lookup:
            return answer
        try:
            hits = self._glossary_lookup(question)
        except Exception as exc:
            logger.warning("Glossary lookup failed: %s", exc)
            return answer
        if not hits:
            return answer
        notes = "; ".join(f"{h.get('term', h.term if hasattr(h, 'term') else '')}: {h.get('definition', getattr(h, 'definition', ''))}" for h in hits)
        if notes and answer.definition:
            answer.definition = f"{answer.definition}\n\n[术语] {notes}"
        elif notes:
            answer.definition = f"[术语] {notes}"
        return answer

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
