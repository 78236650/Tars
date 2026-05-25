"""LLM-based business annotations + metric candidates."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ..models.base import ChatMessage
from .config import InsightBudget
from .retry import retry_call
from .snapshot_utils import format_llm_error

logger = logging.getLogger(__name__)


class LlmSynthesizer:
    def __init__(self, budget: InsightBudget, llm_provider=None):
        self.budget = budget
        self.llm_provider = llm_provider

    async def synthesize(
        self,
        datasource_name: str,
        schema: Dict[str, Any],
        table_stats: Dict[str, Any],
        relations: List[Any],
        table_roles: Dict[str, str],
        target_tables: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str], List[str], str]:
        """
        Returns: (schema_annotations, metric_candidates, open_questions, llm_errors, llm_status)
        """
        batches = self._build_batches(
            schema, table_stats, relations, table_roles, target_tables=target_tables
        )
        if target_tables is not None and len(target_tables) == 0:
            return {}, [], [], [], "ok"
        annotations: Dict[str, Any] = {}
        metrics: List[Dict[str, Any]] = []
        open_questions: List[str] = []
        llm_errors: List[str] = []

        if self.llm_provider is None:
            ann = self._heuristic_annotations(schema, table_roles)
            if target_tables is not None:
                ann = {k: v for k, v in ann.items() if k in set(target_tables)}
            return (
                ann,
                [],
                [],
                [
                    "未配置大模型，已使用规则化表注释；请在鉴数页选择模型后点击「用此模型重新建档」。"
                ],
                "skipped",
            )

        failed_batches = 0
        for batch in batches:
            try:
                part = await retry_call(
                    lambda b=batch: self._call_llm(datasource_name, b),
                    attempts=2,
                    backoff=1.0,
                    label=f"insight_llm_batch[{datasource_name}]",
                )
                annotations.update(part.get("tables") or {})
                metrics.extend(part.get("metric_candidates") or [])
                open_questions.extend(part.get("open_questions") or [])
            except Exception as e:
                failed_batches += 1
                logger.warning("[InsightForge] LLM batch failed: %s", e)
                llm_errors.append(format_llm_error(e))

        if not annotations:
            annotations = self._heuristic_annotations(schema, table_roles)

        llm_errors = list(dict.fromkeys(llm_errors))
        open_questions = list(dict.fromkeys(open_questions))
        if failed_batches == 0:
            llm_status = "ok"
        elif failed_batches < len(batches):
            llm_status = "partial"
        else:
            llm_status = "failed"
        return annotations, metrics, open_questions, llm_errors, llm_status

    def _build_batches(
        self,
        schema: Dict[str, Any],
        table_stats: Dict[str, Any],
        relations: List[Any],
        table_roles: Dict[str, str],
        target_tables: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        tables = schema.get("tables") or {}
        names = list(tables.keys())[: self.budget.max_tables]
        if target_tables is not None:
            target_set = set(target_tables)
            names = [n for n in names if n in target_set]
        batch_size = self.budget.llm_batch_tables
        batches = []
        for i in range(0, len(names), batch_size):
            chunk = names[i : i + batch_size]
            payload = {"tables": {}, "relations": []}
            for t in chunk:
                tdef = tables[t]
                tst = table_stats.get(t)
                cols = {}
                col_stats = {}
                if tst is not None:
                    if hasattr(tst, "columns"):
                        for cn, cs in (tst.columns or {}).items():
                            col_stats[cn] = {
                                "null_rate": cs.null_rate,
                                "distinct_rate": cs.distinct_rate,
                                "sample_values": (cs.sample_values or [])[:3],
                            }
                    elif isinstance(tst, dict):
                        col_stats = tst.get("columns") or {}
                for c in (tdef.get("columns") or [])[:20]:
                    cn = c.get("name", "")
                    cols[cn] = {
                        "type": c.get("type"),
                        "comment": c.get("comment"),
                        "stats": col_stats.get(cn, {}),
                    }
                payload["tables"][t] = {
                    "comment": tdef.get("comment"),
                    "role": table_roles.get(t),
                    "columns": cols,
                    "primary_key": tdef.get("primary_key"),
                }
            for rel in relations:
                fr = rel.from_ref if hasattr(rel, "from_ref") else rel.get("from_ref")
                if fr and fr.split(".")[0] in chunk:
                    payload["relations"].append(
                        {
                            "from": fr,
                            "to": rel.to_ref if hasattr(rel, "to_ref") else rel.get("to_ref"),
                            "confidence": rel.confidence if hasattr(rel, "confidence") else rel.get("confidence"),
                        }
                    )
            batches.append(payload)
        if target_tables is not None and not names:
            return []
        return batches or [{"tables": {}, "relations": []}]

    async def _call_llm(self, datasource_name: str, batch: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""你是企业数据分析师。根据以下数据库统计事实，输出 JSON（不要 markdown 包裹）。

数据源：{datasource_name}

事实数据：
{json.dumps(batch, ensure_ascii=False)[:12000]}

输出 JSON 格式：
{{
  "tables": {{
    "表名": {{
      "description": "业务描述",
      "columns": {{ "列名": "业务含义" }}
    }}
  }},
  "metric_candidates": [
    {{
      "key": "snake_case",
      "display_name": "中文名",
      "definition": "口径说明",
      "sql_template": "SELECT ...",
      "confidence": 0.0-1.0,
      "tables": ["表名"]
    }}
  ],
  "open_questions": ["待业务确认的问题"]
}}

约束：不得编造不存在的表/列；不确定的写入 open_questions。"""

        msg = ChatMessage(role="user", content=prompt)
        response = await self.llm_provider.chat([msg])
        content = response.content if hasattr(response, "content") else str(response)
        return self._parse_json(content)

    def _parse_json(self, content: str) -> Dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                return json.loads(m.group(0))
            raise

    def _heuristic_annotations(
        self, schema: Dict[str, Any], table_roles: Dict[str, str]
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for table, tdef in (schema.get("tables") or {}).items():
            comment = (tdef.get("comment") or "").strip()
            role = table_roles.get(table, "reference")
            desc = comment or f"{role} 表 {table}"
            cols_out = {}
            for c in tdef.get("columns") or []:
                cn = c.get("name", "")
                cc = (c.get("comment") or "").strip()
                cols_out[cn] = cc or cn
            out[table] = {
                "description": desc,
                "columns": cols_out,
                "relationships": "",
            }
        return out


def get_default_llm_provider():
    try:
        from ..models import load_providers_from_config, providers

        if not providers:
            load_providers_from_config()
        from ..models import providers as p

        return p.get("_default")
    except Exception:
        return None
