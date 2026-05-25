"""Batch column statistics SQL for InsightForge (T1 dialects)."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .base import quote_ident, quote_table


def build_batch_stats_sql(
    table: str,
    columns: List[str],
    dialect: str,
) -> str:
    """Build a single SELECT with COUNT(*) + per-column null/distinct stats."""
    t = quote_table(table, dialect)
    parts = ["COUNT(*) AS total"]
    for col in columns:
        c = quote_ident(col, dialect)
        safe = col.replace("`", "").replace('"', "")
        parts.append(f"SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END) AS null_{safe}")
        parts.append(f"COUNT(DISTINCT {c}) AS dist_{safe}")
    return f"SELECT {', '.join(parts)} FROM {t}"


def split_column_batches(columns: List[str], batch_size: int) -> List[List[str]]:
    if batch_size <= 0:
        return [columns]
    return [columns[i : i + batch_size] for i in range(0, len(columns), batch_size)]


def parse_batch_result(
    row: Tuple[Any, ...],
    columns: List[str],
) -> Dict[str, Dict[str, Any]]:
    """Parse batch stats row into per-column null_rate / distinct_count."""
    if not row:
        return {}
    total = int(row[0] or 0)
    out: Dict[str, Dict[str, Any]] = {}
    idx = 1
    for col in columns:
        nulls = int(row[idx] or 0) if idx < len(row) else 0
        distinct = int(row[idx + 1] or 0) if idx + 1 < len(row) else None
        idx += 2
        entry: Dict[str, Any] = {}
        if total > 0:
            entry["null_rate"] = round(nulls / total, 4)
        if distinct is not None:
            entry["distinct_count"] = distinct
            if total > 0:
                entry["distinct_rate"] = round(distinct / total, 4)
        out[col] = entry
    return out
