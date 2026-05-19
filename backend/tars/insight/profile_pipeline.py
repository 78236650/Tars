"""InsightForge Profile pipeline P0-P5."""
from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any, Callable, Dict, List, Optional

from ..database.bi_store import DataSource
from .config import InsightConfig, get_insight_config
from .knowledge_publisher import KnowledgePublisher
from .llm_synthesizer import LlmSynthesizer, get_default_llm_provider
from .relation_inferencer import RelationInferencer
from .role_classifier import RoleClassifier
from .stats_collector import StatsCollector, TableStats
from .version import INS_VERSION

logger = logging.getLogger(__name__)


def _table_stats_to_dict(stats: Dict[str, TableStats]) -> Dict[str, Any]:
    out = {}
    for name, ts in stats.items():
        if is_dataclass(ts):
            d = asdict(ts)
        else:
            d = ts
        out[name] = d
    return out


def _relations_to_dict(relations) -> List[Dict[str, Any]]:
    result = []
    for r in relations:
        if is_dataclass(r):
            result.append(asdict(r))
        else:
            result.append(r)
    return result


class ProfilePipeline:
    def __init__(
        self,
        config: Optional[InsightConfig] = None,
        knowledge_publisher: Optional[KnowledgePublisher] = None,
        llm_provider=None,
        on_progress: Optional[Callable[[str, int, int, str], None]] = None,
    ):
        self.config = config or get_insight_config()
        self.publisher = knowledge_publisher
        self.llm_provider = llm_provider if llm_provider is not None else get_default_llm_provider()
        self.on_progress = on_progress

    def _progress(self, phase: str, current: int, total: int, message: str):
        if self.on_progress:
            self.on_progress(phase, current, total, message)

    async def run(self, datasource: DataSource) -> Dict[str, Any]:
        db_type = datasource.db_type
        profile_mode = self.config.profile_mode_for_db(db_type)
        stats_dialect = self.config.stats_dialect_key(db_type)
        budget = self.config.profile

        collector = StatsCollector(
            datasource.connection_url,
            db_type,
            stats_dialect,
            budget,
        )
        quality_flags: List[Dict[str, Any]] = []

        try:
            self._progress("schema", 0, 5, "抓取 Schema")
            schema = collector.collect_schema()
            if schema.get("error"):
                raise RuntimeError(schema["error"])

            tables = collector.filter_tables(schema)
            total_tables = max(len(tables), 1)

            self._progress("stats", 1, 5, f"统计画像 ({len(tables)} 表)")
            table_stats = collector.collect_all(schema, tables)

            for tname, ts in table_stats.items():
                for cname, cs in ts.columns.items():
                    if cs.null_rate is not None and cs.null_rate > 0.1:
                        quality_flags.append(
                            {
                                "table": tname,
                                "column": cname,
                                "issue": "null_rate_high",
                                "value": cs.null_rate,
                            }
                        )

            self._progress("relations", 2, 5, "推断表关系")
            role_info = RoleClassifier().classify_tables(
                schema, table_stats, budget.core_table_top_n
            )
            core_tables = role_info.get("table_tiers", {}).get("core", tables[: budget.core_table_top_n])
            relations = RelationInferencer().infer(schema, table_stats, core_tables)

            self._progress("synthesize", 3, 5, "生成业务语义")
            synthesizer = LlmSynthesizer(budget, self.llm_provider)
            (
                annotations,
                metric_candidates,
                open_questions,
                llm_errors,
                llm_status,
            ) = await synthesizer.synthesize(
                datasource.name,
                schema,
                table_stats,
                relations,
                role_info.get("table_roles", {}),
            )

            insight_snapshot = {
                "schema_version": 1,
                "capability_version": INS_VERSION,
                "profile_mode": profile_mode,
                "db_type": db_type,
                "stats_dialect": stats_dialect,
                "table_tiers": role_info.get("table_tiers"),
                "table_roles": role_info.get("table_roles"),
                "tables": _table_stats_to_dict(table_stats),
                "relations": _relations_to_dict(relations),
                "quality_flags": quality_flags,
                "open_questions": open_questions,
                "llm_errors": llm_errors,
                "llm_status": llm_status,
                "metric_candidates_count": len(metric_candidates),
            }

            merged_schema = dict(datasource.schema_snapshot or {})
            merged_schema["tables"] = schema.get("tables") or {}
            merged_schema["insight"] = {
                "capability_version": INS_VERSION,
                "profile_mode": profile_mode,
                "last_completed_at": None,
                "table_tiers": role_info.get("table_tiers"),
                "relations": _relations_to_dict(relations),
                "quality_flags": quality_flags,
            }

            knowledge_doc_id = None
            if self.publisher:
                self._progress("publish", 4, 5, "写入知识库")
                md = self.publisher.render_markdown(
                    datasource.name,
                    schema,
                    annotations,
                    relations,
                    role_info.get("table_roles", {}),
                    quality_flags,
                    open_questions,
                    llm_errors=llm_errors,
                )
                knowledge_doc_id = self.publisher.publish(
                    datasource.id,
                    datasource.name,
                    datasource.tenant_id,
                    md,
                )

            self._progress("done", 5, 5, "完成")

            return {
                "success": True,
                "insight_snapshot": insight_snapshot,
                "schema_snapshot": merged_schema,
                "schema_annotations": annotations,
                "metric_candidates": metric_candidates,
                "knowledge_doc_id": knowledge_doc_id,
            }
        finally:
            collector.close()
