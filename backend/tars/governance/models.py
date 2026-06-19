"""治理数据模型 — TARS 风格 dataclass（非 SQLAlchemy ORM）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityRule:
    id: str
    datasource_id: str
    kind: str
    name: str = ""
    table_name: str = ""
    params: dict = field(default_factory=dict)
    engine: str = "builtin"  # "builtin" | "great_expectations"
    enabled: bool = True
    user_id: str = "default"
    created_at: str | None = None


@dataclass
class CheckRun:
    id: str
    datasource_id: str
    table_name: str = ""
    status: str = "pending"  # pending/passed/failed/error
    total_rows: int = 0
    truncated: bool = False
    summary: dict = field(default_factory=dict)
    error: str | None = None
    user_id: str = "default"
    created_at: str | None = None


@dataclass
class RuleResultRow:
    id: str
    check_run_id: str
    rule_id: str
    rule_name: str = ""
    kind: str = ""
    engine: str = "builtin"
    passed_count: int = 0
    failed_count: int = 0
    sample_violations: list[Any] = field(default_factory=list)
