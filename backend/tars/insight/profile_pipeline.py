"""InsightForge Profile pipeline P0-P5."""
from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any, Callable, Dict, List, Optional

from ..database.bi_store import DataSource
from .config import InsightConfig, get_insight_config
from .incremental_planner import IncrementalPlanner
from .knowledge_publisher import KnowledgePublisher
from .llm_synthesizer import LlmSynthesizer, get_default_llm_provider
from .perf_summary import ProfilePerfTracker
from .relation_inferencer import RelationInferencer
from .role_classifier import RoleClassifier
from .schema_fingerprint import fingerprint_schema
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
        d.setdefault("table", name)
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


def _deep_merge_tables(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(old)
    for table, data in new.items():
        if table in merged and isinstance(merged[table], dict) and isinstance(data, dict):
            merged[table] = {**merged[table], **data}
        else:
            merged[table] = data
    return merged


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

    async def run(
        self,
        datasource: DataSource,
        run_id: Optional[str] = None,
        *,
        previous_snapshot: Optional[Dict[str, Any]] = None,
        force: bool = False,
        previous_completed_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        db_type = datasource.db_type
        profile_mode = self.config.profile_mode_for_db(db_type)
        stats_dialect = self.config.stats_dialect_key(db_type)
        budget = self.config.profile
        tracker = ProfilePerfTracker(parallelism=budget.parallel_tables)

        self._progress("preflight", 0, 6, "连接预检")
        tracker.mark_phase("preflight")
        from .preflight import run_preflight

        pf = run_preflight(datasource.connection_url)
        tracker.end_phase("preflight")
        if not pf.ok:
            raise RuntimeError(f"preflight_failed: {pf.reason}; hint: {pf.hint}")

        collector = StatsCollector(
            datasource.connection_url,
            db_type,
            stats_dialect,
            budget,
        )
        quality_flags: List[Dict[str, Any]] = []

        try:
            self._progress("schema", 1, 6, "抓取 Schema")
            tracker.mark_phase("schema")
            schema = collector.collect_schema()
            tracker.end_phase("schema")
            if schema.get("error"):
                raise RuntimeError(schema["error"])

            tables = collector.filter_tables(schema)
            fingerprints = fingerprint_schema(schema)

            planner = IncrementalPlanner(budget)
            plan = planner.plan(
                schema,
                previous_snapshot,
                force=force,
                previous_completed_at=previous_completed_at
                or (previous_snapshot or {}).get("completed_at"),
            )

            self._progress("stats", 2, 6, f"统计画像 ({len(tables)} 表)")
            tracker.mark_phase("stats")
            table_stats: Dict[str, TableStats] = {}
            collect_targets = [
                t for t in tables if plan.actions.get(t, "collect") == "collect"
            ]

            if collect_targets:
                collected, meta = await collector.collect_all_async(
                    schema, collect_targets
                )
                table_stats.update(collected)
                quality_flags.extend(meta.get("quality_flags") or [])
                tracker.merge_stats(meta.get("perf_counters") or {})

            engine = collector._engine_get()
            resampled = 0
            for table in tables:
                action = plan.actions.get(table, "collect")
                if action == "reuse" and previous_snapshot:
                    prev_data = (previous_snapshot.get("tables") or {}).get(table)
                    if prev_data:
                        ts = TableStats.from_dict(prev_data)
                        ts.table = table
                        if budget.incremental_resample_on_reuse:
                            ts.sample_rows = collector.resample_table(engine, table)
                            resampled += 1
                        table_stats[table] = ts

            tracker.set_stat("tables_total", len(tables))
            tracker.set_stat("tables_collected", plan.collected_count)
            tracker.set_stat("tables_reused", plan.reused_count)
            tracker.set_stat("tables_resampled", resampled)
            tracker.set_stat("parallelism", collector._effective_parallelism())
            tracker.end_phase("stats")

            for tname, ts in table_stats.items():
                quality_flags.extend(ts.quality_flags or [])
                if ts.skipped_reason == "table_timeout":
                    quality_flags.append(
                        {"table": tname, "issue": "table_timeout"}
                    )
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

            self._progress("relations", 3, 6, "推断表关系")
            tracker.mark_phase("relations")
            role_info = RoleClassifier().classify_tables(
                schema, table_stats, budget.core_table_top_n
            )
            core_tables = role_info.get("table_tiers", {}).get(
                "core", tables[: budget.core_table_top_n]
            )
            relations = RelationInferencer().infer(schema, table_stats, core_tables)
            tracker.end_phase("relations")

            self._progress("synthesize", 4, 6, "生成业务语义")
            tracker.mark_phase("synthesize")
            synthesizer = LlmSynthesizer(budget, self.llm_provider)
            synthesize_targets = [
                t for t in tables if plan.actions.get(t, "collect") == "collect"
            ]
            annotations: Dict[str, Any] = {}
            if (
                previous_snapshot
                and budget.reuse_synthesize_annotation
                and not force
            ):
                prev_ann = previous_snapshot.get("schema_annotations") or {}
                for t in tables:
                    if plan.actions.get(t) == "reuse" and t in prev_ann:
                        annotations[t] = prev_ann[t]

            reused_ann_count = len(annotations)
            (
                new_annotations,
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
                target_tables=synthesize_targets,
            )
            annotations.update(new_annotations)
            tracker.set_synthesize("tables_llm", len(synthesize_targets))
            tracker.set_synthesize("tables_annotation_reused", reused_ann_count)
            tracker.set_synthesize(
                "batches_sent",
                max(1, (len(synthesize_targets) + budget.llm_batch_tables - 1)
                     // budget.llm_batch_tables) if synthesize_targets else 0,
            )
            tracker.end_phase("synthesize")

            incremental_meta = {
                "reused": plan.reused_count,
                "collected": plan.collected_count,
                "dropped": plan.dropped_count,
                "resampled": resampled,
            }

            from ..database.base import get_local_now

            completed_at = get_local_now().isoformat()

            insight_snapshot = {
                "schema_version": 1,
                "capability_version": INS_VERSION,
                "profile_mode": profile_mode,
                "profile_run_type": plan.profile_run_type,
                "incremental": incremental_meta,
                "db_type": db_type,
                "stats_dialect": stats_dialect,
                "fingerprints": fingerprints,
                "table_tiers": role_info.get("table_tiers"),
                "table_roles": role_info.get("table_roles"),
                "tables": _table_stats_to_dict(table_stats),
                "relations": _relations_to_dict(relations),
                "quality_flags": quality_flags,
                "open_questions": open_questions,
                "llm_errors": llm_errors,
                "llm_status": llm_status,
                "heuristic_used": llm_status in ("skipped", "failed"),
                "metric_candidates_count": len(metric_candidates),
                "schema_annotations": annotations,
                "perf": tracker.to_dict(),
                "completed_at": completed_at,
            }

            merged_schema = dict(datasource.schema_snapshot or {})
            merged_schema["tables"] = _deep_merge_tables(
                merged_schema.get("tables") or {},
                schema.get("tables") or {},
            )
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
                self._progress("publish", 5, 6, "写入知识库")
                tracker.mark_phase("publish")
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
                    md,
                    tenant_id=datasource.tenant_id,
                    run_id=run_id,
                )
                tracker.end_phase("publish")

            self._progress("done", 6, 6, "完成")
            logger.info(
                "[InsightForge/INS-2.1] profile perf ds=%s total_ms=%s collected=%s reused=%s resampled=%s",
                datasource.id,
                insight_snapshot["perf"].get("total_ms"),
                plan.collected_count,
                plan.reused_count,
                resampled,
            )

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
