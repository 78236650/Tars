"""SQL-based column statistics for InsightForge Profile."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ..bi.schema_explorer import SchemaExplorer
from .config import InsightBudget
from .dialects.base import get_dialect_helper
from .sampler import fetch_sample_rows


@dataclass
class ColumnStats:
    name: str
    db_type: str = ""
    null_rate: Optional[float] = None
    distinct_count: Optional[int] = None
    distinct_rate: Optional[float] = None
    sample_values: List[str] = field(default_factory=list)
    enum_top: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TableStats:
    table: str
    row_estimate: Optional[int] = None
    columns: Dict[str, ColumnStats] = field(default_factory=dict)
    elapsed_ms: int = 0
    skipped_reason: Optional[str] = None
    sample_rows: List[Dict[str, Any]] = field(default_factory=list)


class StatsCollector:
    def __init__(
        self,
        connection_url: str,
        db_type: str,
        stats_dialect: str,
        budget: InsightBudget,
    ):
        self.connection_url = connection_url
        self.db_type = db_type
        self.stats_dialect = stats_dialect
        self.budget = budget
        self._engine: Optional[Engine] = None

    def _engine_get(self) -> Engine:
        if self._engine is None:
            kwargs: dict = {}
            if self.connection_url.startswith("sqlite"):
                kwargs["connect_args"] = {"check_same_thread": False}
            else:
                kwargs["connect_args"] = {"connect_timeout": 10}
            self._engine = create_engine(self.connection_url, **kwargs)
        return self._engine

    def close(self):
        if self._engine:
            self._engine.dispose()
            self._engine = None

    def collect_schema(self) -> Dict[str, Any]:
        with SchemaExplorer(self.connection_url) as explorer:
            return explorer.explore()

    def filter_tables(self, schema: Dict[str, Any]) -> List[str]:
        tables = list((schema.get("tables") or {}).keys())
        patterns = [re.compile(p) for p in self.budget.skip_table_patterns]
        filtered = []
        for t in tables:
            if any(p.search(t) for p in patterns):
                continue
            filtered.append(t)
        filtered.sort()
        if len(filtered) > self.budget.max_tables:
            # rank by column count as proxy until row counts known
            filtered = filtered[: self.budget.max_tables]
        return filtered

    def collect_all(self, schema: Dict[str, Any], table_names: Optional[List[str]] = None) -> Dict[str, TableStats]:
        engine = self._engine_get()
        helper = get_dialect_helper(engine, self.stats_dialect, self.db_type)
        tables = table_names or self.filter_tables(schema)
        table_defs = schema.get("tables") or {}

        # Re-rank by row estimate when possible
        estimates: List[tuple] = []
        for t in tables:
            est = helper.estimate_row_count(t)
            estimates.append((t, est or 0))
        estimates.sort(key=lambda x: x[1], reverse=True)
        if len(estimates) > self.budget.max_tables:
            estimates = estimates[: self.budget.max_tables]
        ordered_tables = [t for t, _ in estimates]

        out: Dict[str, TableStats] = {}
        for table in ordered_tables:
            tdef = table_defs.get(table) or {}
            columns = tdef.get("columns") or []
            out[table] = self.collect_table(engine, helper, table, columns)
        return out

    def collect_table(
        self,
        engine: Engine,
        helper,
        table: str,
        columns: List[Dict[str, Any]],
    ) -> TableStats:
        start = time.time()
        stats = TableStats(table=table)
        try:
            stats.row_estimate = helper.estimate_row_count(table)
        except Exception:
            pass

        col_limit = self.budget.max_columns_per_table
        for col in columns[:col_limit]:
            cname = col.get("name", "")
            if not cname:
                continue
            cstats = self._collect_column(helper, table, cname, col)
            stats.columns[cname] = cstats

        try:
            stats.sample_rows = fetch_sample_rows(
                engine,
                table,
                min(50, self.budget.sample_rows_per_table),
                self.stats_dialect,
                self.db_type,
            )
        except Exception:
            pass

        stats.elapsed_ms = int((time.time() - start) * 1000)
        if stats.elapsed_ms > self.budget.table_timeout_sec * 1000:
            stats.skipped_reason = "table_timeout"
        return stats

    def _collect_column(
        self, helper, table: str, column: str, col_meta: Dict[str, Any]
    ) -> ColumnStats:
        cstats = ColumnStats(name=column, db_type=str(col_meta.get("type", "")))
        try:
            stats_sql, sample_sql = helper.column_stats_sql(table, column)
        except ValueError:
            return cstats

        try:
            with helper.engine.connect() as conn:
                result = conn.execute(text(stats_sql)).fetchone()
                if result:
                    total = int(result[0] or 0)
                    nulls = int(result[1] or 0)
                    distinct = int(result[2] or 0) if len(result) > 2 else None
                    if total > 0:
                        cstats.null_rate = round(nulls / total, 4)
                    if distinct is not None:
                        cstats.distinct_count = distinct
                        if total > 0:
                            cstats.distinct_rate = round(distinct / total, 4)
                samp = conn.execute(text(sample_sql)).fetchall()
                cstats.sample_values = [str(r[0])[:80] for r in samp[:5]]
        except Exception:
            pass
        return cstats
