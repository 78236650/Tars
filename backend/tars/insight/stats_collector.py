"""SQL-based column statistics for InsightForge Profile."""
from __future__ import annotations

import asyncio
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ..bi.schema_explorer import SchemaExplorer
from .config import InsightBudget
from .dialects.base import get_dialect_helper
from .dialects.batch_stats import (
    build_batch_stats_sql,
    parse_batch_result,
    split_column_batches,
)
from .sampler import fetch_sample_rows
from .sql_timeout import SqlTimeoutExecutor


@dataclass
class ColumnStats:
    name: str
    db_type: str = ""
    null_rate: Optional[float] = None
    distinct_count: Optional[int] = None
    distinct_rate: Optional[float] = None
    sample_values: List[str] = field(default_factory=list)
    enum_top: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ColumnStats":
        return cls(
            name=data.get("name", ""),
            db_type=str(data.get("db_type", "")),
            null_rate=data.get("null_rate"),
            distinct_count=data.get("distinct_count"),
            distinct_rate=data.get("distinct_rate"),
            sample_values=list(data.get("sample_values") or []),
            enum_top=list(data.get("enum_top") or []),
        )


@dataclass
class TableStats:
    table: str
    row_estimate: Optional[int] = None
    columns: Dict[str, ColumnStats] = field(default_factory=dict)
    elapsed_ms: int = 0
    skipped_reason: Optional[str] = None
    sample_rows: List[Dict[str, Any]] = field(default_factory=list)
    quality_flags: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "TableStats":
        cols = {}
        for name, cdata in (data.get("columns") or {}).items():
            cd = dict(cdata)
            cd.setdefault("name", name)
            cols[name] = ColumnStats.from_dict(cd)
        return cls(
            table=data.get("table", ""),
            row_estimate=data.get("row_estimate"),
            columns=cols,
            elapsed_ms=int(data.get("elapsed_ms") or 0),
            skipped_reason=data.get("skipped_reason"),
            sample_rows=list(data.get("sample_rows") or []),
            quality_flags=list(data.get("quality_flags") or []),
        )


class StatsCollector:
    def __init__(
        self,
        connection_url: str,
        db_type: str,
        stats_dialect: str,
        budget: InsightBudget,
    ):
        from ..utils.url_safety import validate_external_db_url

        validate_external_db_url(connection_url)
        self.connection_url = connection_url
        self.db_type = db_type
        self.stats_dialect = stats_dialect
        self.budget = budget
        self._engine: Optional[Engine] = None
        self._sql_exec = SqlTimeoutExecutor(
            timeout_sec=budget.stats_timeout_sec,
            dialect=stats_dialect,
        )
        self.perf_counters: Dict[str, int] = {
            "sql_executed": 0,
            "sql_batch_used": 0,
            "sql_fallback_single": 0,
            "columns_timed_out": 0,
        }
        self._perf_lock = threading.Lock()

    def _bump(self, key: str, delta: int = 1) -> None:
        with self._perf_lock:
            self.perf_counters[key] = self.perf_counters.get(key, 0) + delta

    def _snapshot_perf(self) -> Dict[str, int]:
        with self._perf_lock:
            return dict(self.perf_counters)

    def _engine_get(self) -> Engine:
        if self._engine is None:
            kwargs: dict = {}
            if self.connection_url.startswith("sqlite"):
                kwargs["connect_args"] = {"check_same_thread": False}
            else:
                parallel = self.budget.parallel_tables
                pool_size = max(parallel + 2, 5)
                max_overflow = max(parallel, 5)
                kwargs["pool_size"] = pool_size
                kwargs["max_overflow"] = max_overflow
                kwargs["pool_pre_ping"] = True
                kwargs["connect_args"] = (
                    {"connect_timeout": 10, "charset": "utf8mb4"}
                    if (
                        self.connection_url.startswith("mysql")
                        or "pymysql" in self.connection_url
                    )
                    else {"connect_timeout": 10}
                )
            self._engine = create_engine(self.connection_url, **kwargs)
        return self._engine

    def close(self):
        if self._engine:
            self._engine.dispose()
            self._engine = None
        self._sql_exec.close()

    def _effective_parallelism(self) -> int:
        if self.db_type == "sqlite" or self.connection_url.startswith("sqlite"):
            return 1
        parallel = min(self.budget.parallel_tables, self.budget.parallel_tables_max)
        return max(1, parallel)

    def _batch_enabled(self) -> bool:
        if os.environ.get("TARS_INSIGHT_DISABLE_BATCH_SQL") == "1":
            return False
        return self.stats_dialect in ("mysql", "doris", "postgresql", "sqlite")

    def _batch_size_for_table(self, helper, table: str) -> int:
        base = self.budget.column_stats_batch_size
        if self.stats_dialect == "postgresql":
            try:
                est = helper.estimate_row_count(table) or 0
                if est > 100_000:
                    return 1
                else:
                    return min(base, self.budget.column_stats_batch_size_pg_max)
            except Exception:
                pass
        return base

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
            filtered = filtered[: self.budget.max_tables]
        return filtered

    def _rank_tables(
        self,
        schema: Dict[str, Any],
        helper,
        table_names: Optional[List[str]] = None,
    ) -> List[str]:
        tables = table_names or self.filter_tables(schema)
        estimates: List[tuple] = []
        for t in tables:
            est = helper.estimate_row_count(t)
            estimates.append((t, est or 0))
        estimates.sort(key=lambda x: x[1], reverse=True)
        if len(estimates) > self.budget.max_tables:
            estimates = estimates[: self.budget.max_tables]
        return [t for t, _ in estimates]

    def collect_all(
        self, schema: Dict[str, Any], table_names: Optional[List[str]] = None
    ) -> Dict[str, TableStats]:
        engine = self._engine_get()
        helper = get_dialect_helper(engine, self.stats_dialect, self.db_type)
        ordered_tables = self._rank_tables(schema, helper, table_names)
        table_defs = schema.get("tables") or {}
        out: Dict[str, TableStats] = {}
        for table in ordered_tables:
            tdef = table_defs.get(table) or {}
            columns = tdef.get("columns") or []
            out[table] = self.collect_table(engine, helper, table, columns)
        return out

    async def collect_all_async(
        self,
        schema: Dict[str, Any],
        table_names: Optional[List[str]] = None,
        *,
        track_concurrency: bool = False,
    ) -> Tuple[Dict[str, TableStats], dict]:
        engine = self._engine_get()
        helper = get_dialect_helper(engine, self.stats_dialect, self.db_type)
        ordered_tables = self._rank_tables(schema, helper, table_names)
        table_defs = schema.get("tables") or {}
        sem = asyncio.Semaphore(self._effective_parallelism())
        inflight = 0
        max_inflight = 0
        lock = asyncio.Lock()
        quality_flags: List[Dict[str, Any]] = []

        async def one(table: str):
            nonlocal inflight, max_inflight
            async with sem:
                if track_concurrency:
                    async with lock:
                        inflight += 1
                        max_inflight = max(max_inflight, inflight)
                try:
                    tdef = table_defs.get(table) or {}
                    columns = tdef.get("columns") or []
                    ts = await asyncio.to_thread(
                        self.collect_table, engine, helper, table, columns
                    )
                    return table, ts
                finally:
                    if track_concurrency:
                        async with lock:
                            inflight -= 1

        pairs = await asyncio.gather(
            *[one(t) for t in ordered_tables], return_exceptions=True
        )
        out: Dict[str, TableStats] = {}
        for entry in pairs:
            if isinstance(entry, Exception):
                quality_flags.append(
                    {"issue": "table_collect_error", "detail": str(entry)[:200]}
                )
                continue
            t, ts = entry
            out[t] = ts
            if ts.quality_flags:
                quality_flags.extend(ts.quality_flags)
        meta = {
            "max_inflight": max_inflight,
            "quality_flags": quality_flags,
            "perf_counters": self._snapshot_perf(),
        }
        return out, meta

    def collect_table(
        self,
        engine: Engine,
        helper,
        table: str,
        columns: List[Dict[str, Any]],
    ) -> TableStats:
        start = time.time()
        stats = TableStats(table=table)
        quality_flags: List[Dict[str, Any]] = []
        try:
            stats.row_estimate = helper.estimate_row_count(table)
            self._bump("sql_executed")
        except Exception:
            pass

        col_limit = self.budget.max_columns_per_table
        col_names = [
            c.get("name", "")
            for c in columns[:col_limit]
            if c.get("name")
        ]
        col_meta = {c.get("name", ""): c for c in columns[:col_limit] if c.get("name")}

        if self._batch_enabled() and col_names:
            batch_ok = self._collect_columns_batch(
                helper, table, col_names, col_meta, stats, quality_flags, start
            )
            if not batch_ok:
                self._collect_columns_single(
                    helper, table, col_names, col_meta, stats, quality_flags, start
                )
        else:
            self._collect_columns_single(
                helper, table, col_names, col_meta, stats, quality_flags, start
            )

        try:
            stats.sample_rows = fetch_sample_rows(
                engine,
                table,
                min(50, self.budget.sample_rows_per_table),
                self.stats_dialect,
                self.db_type,
            )
            self._bump("sql_executed")
        except Exception:
            pass

        stats.elapsed_ms = int((time.time() - start) * 1000)
        if stats.elapsed_ms > self.budget.table_timeout_sec * 1000 and not stats.skipped_reason:
            stats.skipped_reason = "table_timeout"
        stats.quality_flags = quality_flags
        return stats

    def _table_wall_exceeded(self, start: float) -> bool:
        return (time.time() - start) > self.budget.table_timeout_sec

    def _collect_columns_batch(
        self,
        helper,
        table: str,
        col_names: List[str],
        col_meta: Dict[str, dict],
        stats: TableStats,
        quality_flags: List[Dict[str, Any]],
        start: float,
    ) -> bool:
        batch_size = self._batch_size_for_table(helper, table)
        batches = split_column_batches(col_names, batch_size)
        try:
            for batch_cols in batches:
                if self._table_wall_exceeded(start):
                    stats.skipped_reason = "table_timeout"
                    break
                sql = build_batch_stats_sql(table, batch_cols, helper.name)
                if len(sql) > 8000:
                    return False
                row = self._sql_exec.fetch_one(helper.engine, sql)
                self._bump("sql_executed")
                self._bump("sql_batch_used")
                if row is None:
                    quality_flags.append({"table": table, "issue": "batch_fallback"})
                    return False
                parsed = parse_batch_result(tuple(row), batch_cols)
                for cname in batch_cols:
                    pdata = parsed.get(cname, {})
                    cstats = ColumnStats(
                        name=cname,
                        db_type=str(col_meta.get(cname, {}).get("type", "")),
                        null_rate=pdata.get("null_rate"),
                        distinct_count=pdata.get("distinct_count"),
                        distinct_rate=pdata.get("distinct_rate"),
                    )
                    self._fill_sample_values(helper, table, cname, cstats, start)
                    stats.columns[cname] = cstats
            for cname in col_names:
                if cname not in stats.columns:
                    cstats, flag = self._collect_column(
                        helper, table, cname, col_meta.get(cname, {})
                    )
                    stats.columns[cname] = cstats
                    if flag:
                        quality_flags.append(flag)
            return True
        except Exception:
            quality_flags.append({"table": table, "issue": "batch_fallback"})
            stats.columns.clear()
            return False

    def _collect_columns_single(
        self,
        helper,
        table: str,
        col_names: List[str],
        col_meta: Dict[str, dict],
        stats: TableStats,
        quality_flags: List[Dict[str, Any]],
        start: float,
    ) -> None:
        for cname in col_names:
            if self._table_wall_exceeded(start):
                stats.skipped_reason = "table_timeout"
                break
            cstats, flag = self._collect_column(
                helper, table, cname, col_meta.get(cname, {})
            )
            stats.columns[cname] = cstats
            if flag:
                quality_flags.append(flag)

    def _fill_sample_values(
        self, helper, table: str, column: str, cstats: ColumnStats, start: float
    ) -> None:
        if self._table_wall_exceeded(start):
            return
        try:
            _, sample_sql = helper.column_stats_sql(table, column)
            samp = self._sql_exec.fetch_all(helper.engine, sample_sql)
            self._bump("sql_executed")
            if samp:
                cstats.sample_values = [str(r[0])[:80] for r in samp[:5]]
        except Exception:
            pass

    def _collect_column(
        self, helper, table: str, column: str, col_meta: Dict[str, Any]
    ) -> Tuple[ColumnStats, Optional[Dict[str, Any]]]:
        cstats = ColumnStats(name=column, db_type=str(col_meta.get("type", "")))
        quality_flag = None
        try:
            stats_sql, sample_sql = helper.column_stats_sql(table, column)
        except ValueError:
            return cstats, None

        self._bump("sql_fallback_single")
        result = self._sql_exec.fetch_one(helper.engine, stats_sql)
        self._bump("sql_executed")
        if result is None:
            self._bump("columns_timed_out")
            quality_flag = {
                "table": table,
                "column": column,
                "issue": "stats_timeout",
            }
            return cstats, quality_flag

        total = int(result[0] or 0)
        nulls = int(result[1] or 0)
        distinct = int(result[2] or 0) if len(result) > 2 else None
        if total > 0:
            cstats.null_rate = round(nulls / total, 4)
        if distinct is not None:
            cstats.distinct_count = distinct
            if total > 0:
                cstats.distinct_rate = round(distinct / total, 4)

        samp = self._sql_exec.fetch_all(helper.engine, sample_sql)
        self._bump("sql_executed")
        if samp:
            cstats.sample_values = [str(r[0])[:80] for r in samp[:5]]
        return cstats, quality_flag

    def resample_table(
        self, engine: Engine, table: str
    ) -> List[Dict[str, Any]]:
        """Re-fetch sample rows for incremental reuse (1 SQL per table)."""
        try:
            rows = fetch_sample_rows(
                engine,
                table,
                min(50, self.budget.sample_rows_per_table),
                self.stats_dialect,
                self.db_type,
            )
            self._bump("sql_executed")
            return rows
        except Exception:
            return []
