"""Load InsightForge configuration from insight.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

import yaml

from .version import INS_VERSION


@dataclass
class InsightBudget:
    max_tables: int = 80
    max_columns_per_table: int = 60
    sample_rows_per_table: int = 500
    core_table_top_n: int = 20
    stats_timeout_sec: int = 15
    table_timeout_sec: int = 120
    parallel_tables: int = 3
    llm_batch_tables: int = 8
    llm_max_tokens_per_batch: int = 6000
    skip_table_patterns: List[str] = field(default_factory=lambda: ["^_", "^tmp_", "^bak_"])
    enable_incremental: bool = True
    incremental_ttl_hours: int = 24


@dataclass
class InsightForgeSettings:
    pending_question_ttl_seconds: int = 1800


@dataclass
class InsightQaSettings:
    fewshot_max_items: int = 5
    fewshot_max_tokens: int = 2000
    fewshot_recall_timeout_ms: int = 200
    allow_ad_hoc_sql: bool = True
    max_sql_rows: int = 1000
    sql_timeout_sec: int = 30
    require_metric_citation: bool = True


@dataclass
class InsightAdoptionSettings:
    require_review: bool = False
    publish_to_knowledge: bool = True


@dataclass
class InsightFeedbackSettings:
    downgrade_window_days: int = 30
    downgrade_min_down: int = 3
    downgrade_ratio_min: float = 0.30
    downgrade_cooldown_days: int = 7


@dataclass
class InsightFeatureFlags:
    chat_first_enabled: bool = False


@dataclass
class InsightConfig:
    capability_name: str = "insight-forge"
    version: str = INS_VERSION
    tier1_databases: List[str] = field(
        default_factory=lambda: ["oracle", "mysql", "postgresql", "doris"]
    )
    tier2_databases: List[str] = field(default_factory=lambda: ["jdbc"])
    profile: InsightBudget = field(default_factory=InsightBudget)
    forge: InsightForgeSettings = field(default_factory=InsightForgeSettings)
    qa: InsightQaSettings = field(default_factory=InsightQaSettings)
    adoption: InsightAdoptionSettings = field(default_factory=InsightAdoptionSettings)
    feedback: InsightFeedbackSettings = field(default_factory=InsightFeedbackSettings)
    feature_flags: InsightFeatureFlags = field(default_factory=InsightFeatureFlags)
    metric_qa: dict = field(default_factory=dict)
    publish: dict = field(default_factory=dict)

    def profile_mode_for_db(self, db_type: str) -> str:
        normalized = (db_type or "").lower()
        if normalized in self.tier1_databases:
            return "full"
        if normalized in self.tier2_databases:
            return "generic"
        if normalized in ("sqlserver", "clickhouse", "sqlite"):
            return "full"
        return "generic"

    def stats_dialect_key(self, db_type: str) -> str:
        """Map logical db_type to stats collector implementation."""
        normalized = (db_type or "").lower()
        if normalized == "doris":
            return "mysql"
        return normalized


def _config_path() -> Path:
    return Path(__file__).parent.parent.parent / "config" / "insight.yaml"


def load_insight_config(path: str | Path | None = None) -> InsightConfig:
    cfg_path = Path(path) if path else _config_path()
    if not cfg_path.exists():
        return InsightConfig()

    with open(cfg_path, encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    cap = raw.get("capability") or {}
    dbs = raw.get("databases") or {}
    prof = raw.get("profile") or {}
    forge_raw = raw.get("forge") or {}
    qa_raw = raw.get("qa") or {}
    metric_qa_raw = dict(raw.get("metric_qa") or {})
    adoption_raw = raw.get("adoption") or {}
    feedback_raw = raw.get("feedback") or {}
    flags_raw = raw.get("feature_flags") or {}

    budget = InsightBudget(
        max_tables=int(prof.get("max_tables", 80)),
        max_columns_per_table=int(prof.get("max_columns_per_table", 60)),
        sample_rows_per_table=int(prof.get("sample_rows_per_table", 500)),
        core_table_top_n=int(prof.get("core_table_top_n", 20)),
        stats_timeout_sec=int(prof.get("stats_timeout_sec", 15)),
        table_timeout_sec=int(prof.get("table_timeout_sec", 120)),
        parallel_tables=int(prof.get("parallel_tables", 3)),
        llm_batch_tables=int(prof.get("llm_batch_tables", 8)),
        llm_max_tokens_per_batch=int(prof.get("llm_max_tokens_per_batch", 6000)),
        skip_table_patterns=list(prof.get("skip_table_patterns") or ["^_", "^tmp_", "^bak_"]),
        enable_incremental=bool(prof.get("enable_incremental", True)),
        incremental_ttl_hours=int(prof.get("incremental_ttl_hours", 24)),
    )

    qa = InsightQaSettings(
        fewshot_max_items=int(qa_raw.get("fewshot_max_items", 5)),
        fewshot_max_tokens=int(qa_raw.get("fewshot_max_tokens", 2000)),
        fewshot_recall_timeout_ms=int(qa_raw.get("fewshot_recall_timeout_ms", 200)),
        allow_ad_hoc_sql=bool(
            qa_raw.get("allow_ad_hoc_sql", metric_qa_raw.get("allow_ad_hoc_sql", True))
        ),
        max_sql_rows=int(metric_qa_raw.get("max_sql_rows", 1000)),
        sql_timeout_sec=int(metric_qa_raw.get("sql_timeout_sec", 30)),
        require_metric_citation=bool(metric_qa_raw.get("require_metric_citation", True)),
    )

    return InsightConfig(
        capability_name=str(cap.get("name", "insight-forge")),
        version=str(cap.get("version", INS_VERSION)),
        tier1_databases=list(dbs.get("tier1") or ["oracle", "mysql", "postgresql", "doris"]),
        tier2_databases=list(dbs.get("tier2") or ["jdbc"]),
        profile=budget,
        forge=InsightForgeSettings(
            pending_question_ttl_seconds=int(
                forge_raw.get("pending_question_ttl_seconds", 1800)
            ),
        ),
        qa=qa,
        adoption=InsightAdoptionSettings(
            require_review=bool(adoption_raw.get("require_review", False)),
            publish_to_knowledge=bool(adoption_raw.get("publish_to_knowledge", True)),
        ),
        feedback=InsightFeedbackSettings(
            downgrade_window_days=int(feedback_raw.get("downgrade_window_days", 30)),
            downgrade_min_down=int(feedback_raw.get("downgrade_min_down", 3)),
            downgrade_ratio_min=float(feedback_raw.get("downgrade_ratio_min", 0.30)),
            downgrade_cooldown_days=int(feedback_raw.get("downgrade_cooldown_days", 7)),
        ),
        feature_flags=InsightFeatureFlags(
            chat_first_enabled=bool(flags_raw.get("chat_first_enabled", False)),
        ),
        metric_qa=metric_qa_raw,
        publish=dict(raw.get("publish") or {}),
    )


_insight_config: InsightConfig | None = None


def get_insight_config() -> InsightConfig:
    global _insight_config
    if _insight_config is None:
        _insight_config = load_insight_config()
    return _insight_config
