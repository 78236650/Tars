"""Apply dialect-aware identifier quoting to metric SQL (P1 #4)."""
from __future__ import annotations

import re
from typing import List

from .dialects.base import quote_table


def bi_db_type_to_quote_dialect(db_type: str) -> str:
    normalized = (db_type or "").lower()
    if normalized in ("mysql", "doris", "clickhouse"):
        return "mysql"
    if normalized in ("postgresql", "postgres"):
        return "postgresql"
    if normalized == "oracle":
        return "oracle"
    if normalized in ("sqlserver", "mssql"):
        return "sqlserver"
    return "generic"


def apply_tables_quoting(sql: str, tables: List[str], db_type: str) -> str:
    """Quote known table identifiers in SQL templates before execution."""
    if not sql or not tables:
        return sql

    dialect = bi_db_type_to_quote_dialect(db_type)
    out = sql
    seen_lower: set[str] = set()

    for table in sorted({t.strip() for t in tables if t and t.strip()}, key=len, reverse=True):
        key = table.lower()
        if key in seen_lower:
            continue
        seen_lower.add(key)
        try:
            quoted = quote_table(table, dialect)
        except ValueError:
            continue
        if quoted in out:
            continue
        pattern = re.compile(
            rf"(?<![`'\"])\b{re.escape(table)}\b(?![`'\"])",
            re.IGNORECASE,
        )
        out = pattern.sub(quoted, out)
    return out
