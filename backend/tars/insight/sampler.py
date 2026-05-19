"""Table sampling utilities for InsightForge."""
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .dialects.base import get_dialect_helper


def fetch_sample_rows(
    engine: Engine,
    table: str,
    limit: int,
    stats_dialect: str,
    logical_db_type: str,
) -> List[Dict[str, Any]]:
    helper = get_dialect_helper(engine, stats_dialect, logical_db_type)
    sql = helper.sample_sql(table, limit)
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            cols = list(result.keys())
            rows = []
            for row in result:
                rows.append({cols[i]: _serialize(row[i]) for i in range(len(cols))})
                if len(rows) >= limit:
                    break
            return rows
    except Exception:
        return []


def _serialize(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (int, float, bool, str)):
        return val
    return str(val)[:200]
