"""SQL dialect helpers for InsightForge stats collection."""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Accept Unicode word chars, digits, dots (for schema.table), hyphens, spaces.
# Reject quote characters that could break quoting.
_UNSAFE_CHARS = re.compile(r'[\'";\\`]')


def quote_ident(name: str, dialect: str = "generic") -> str:
    """Quote a single identifier segment. Rejects embedded quote chars."""
    if not name or _UNSAFE_CHARS.search(name):
        logger.warning("Rejected unsafe identifier: %r", name)
        raise ValueError(f"unsafe identifier: {name!r}")
    if dialect in ("mysql", "doris"):
        return f"`{name}`"
    return f'"{name}"'


def quote_table(table: str, dialect: str = "generic") -> str:
    """Quote a potentially multi-part table name (db.schema.table)."""
    parts = table.split(".")
    return ".".join(quote_ident(p, dialect) for p in parts)


class DialectHelper(ABC):
    name: str = "generic"

    def __init__(self, engine: Engine, logical_db_type: str):
        self.engine = engine
        self.logical_db_type = logical_db_type

    def fetch_scalar(self, sql: str, params: Optional[dict] = None) -> Any:
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), params or {}).fetchone()
            return row[0] if row else None

    @abstractmethod
    def estimate_row_count(self, table: str) -> Optional[int]:
        ...

    def sample_sql(self, table: str, limit: int) -> str:
        t = quote_table(table, self.name)
        if self.name in ("mysql", "doris"):
            return f"SELECT * FROM {t} ORDER BY RAND() LIMIT {int(limit)}"
        if self.name == "postgresql":
            return f"SELECT * FROM {t} TABLESAMPLE BERNOULLI (1) REPEATABLE (42) LIMIT {int(limit)}"
        return f"SELECT * FROM {t} LIMIT {int(limit)}"

    def column_stats_sql(self, table: str, column: str) -> Tuple[str, str]:
        """Return (stats_sql, sample_values_sql)."""
        t = quote_table(table, self.name)
        c = quote_ident(column, self.name)
        stats = (
            f"SELECT COUNT(*) AS total, "
            f"SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END) AS nulls, "
            f"COUNT(DISTINCT {c}) AS distinct_count "
            f"FROM {t}"
        )
        sample = f"SELECT DISTINCT {c} AS v FROM {t} WHERE {c} IS NOT NULL LIMIT 5"
        return stats, sample


class GenericDialectHelper(DialectHelper):
    name = "generic"

    def estimate_row_count(self, table: str) -> Optional[int]:
        try:
            t = quote_table(table, self.name)
            val = self.fetch_scalar(f"SELECT COUNT(*) FROM {t}")
            return int(val) if val is not None else None
        except Exception:
            return None


class MysqlDialectHelper(DialectHelper):
    name = "mysql"

    def estimate_row_count(self, table: str) -> Optional[int]:
        try:
            val = self.fetch_scalar(
                """
                SELECT TABLE_ROWS FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tname
                """,
                {"tname": table.split(".")[-1]},
            )
            if val is not None:
                return int(val)
        except Exception:
            pass
        return super().estimate_row_count(table)


class PostgresqlDialectHelper(DialectHelper):
    name = "postgresql"

    def estimate_row_count(self, table: str) -> Optional[int]:
        try:
            t = table.split(".")[-1]
            val = self.fetch_scalar(
                """
                SELECT reltuples::bigint FROM pg_class
                WHERE relname = :tname
                """,
                {"tname": t},
            )
            if val is not None and int(val) >= 0:
                return int(val)
        except Exception:
            pass
        return super().estimate_row_count(table)


class OracleDialectHelper(DialectHelper):
    name = "oracle"

    def estimate_row_count(self, table: str) -> Optional[int]:
        try:
            t = table.upper().split(".")[-1]
            val = self.fetch_scalar(
                """
                SELECT NUM_ROWS FROM ALL_TABLES
                WHERE TABLE_NAME = :tname AND ROWNUM = 1
                """,
                {"tname": t},
            )
            if val is not None:
                return int(val)
        except Exception:
            pass
        return super().estimate_row_count(table)


def get_dialect_helper(engine: Engine, stats_dialect: str, logical_db_type: str) -> DialectHelper:
    key = (stats_dialect or logical_db_type or "generic").lower()
    if key in ("mysql", "doris"):
        return MysqlDialectHelper(engine, logical_db_type)
    if key == "postgresql":
        return PostgresqlDialectHelper(engine, logical_db_type)
    if key == "oracle":
        return OracleDialectHelper(engine, logical_db_type)
    return GenericDialectHelper(engine, logical_db_type)
