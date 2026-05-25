"""SQL statement timeout wrapper for InsightForge stats collection."""
from __future__ import annotations

import concurrent.futures
import re
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine


class SqlTimeoutExecutor:
    def __init__(self, timeout_sec: int = 15, dialect: str = "generic"):
        self.timeout_sec = timeout_sec
        self.dialect = (dialect or "generic").lower()
        self._pool: concurrent.futures.ThreadPoolExecutor | None = None

    def fetch_one(
        self, engine: Engine, sql: str, params: Optional[dict] = None
    ) -> Any | None:
        rows = self._execute(engine, sql, params, fetch="one")
        return rows

    def fetch_all(
        self, engine: Engine, sql: str, params: Optional[dict] = None
    ) -> list | None:
        rows = self._execute(engine, sql, params, fetch="all")
        return rows if rows is not None else None

    def _execute(
        self,
        engine: Engine,
        sql: str,
        params: Optional[dict],
        *,
        fetch: str,
    ) -> Any | None:
        if self.dialect == "postgresql":
            return self._pg_execute(engine, sql, params, fetch=fetch)
        if self.dialect in ("mysql", "doris"):
            return self._mysql_execute(engine, sql, params, fetch=fetch)
        return self._thread_timeout_execute(engine, sql, params, fetch=fetch)

    def _pg_execute(
        self, engine: Engine, sql: str, params: Optional[dict], *, fetch: str
    ) -> Any | None:
        ms = self.timeout_sec * 1000
        try:
            with engine.connect() as conn:
                with conn.begin():
                    conn.execute(text(f"SET LOCAL statement_timeout = '{ms}'"))
                    result = conn.execute(text(sql), params or {})
                    if fetch == "one":
                        return result.fetchone()
                    return result.fetchall()
        except Exception:
            return None

    def _mysql_execute(
        self, engine: Engine, sql: str, params: Optional[dict], *, fetch: str
    ) -> Any | None:
        ms = self.timeout_sec * 1000
        hinted = self._inject_mysql_hint(sql, ms)
        try:
            with engine.connect() as conn:
                result = conn.execute(text(hinted), params or {})
                if fetch == "one":
                    return result.fetchone()
                return result.fetchall()
        except Exception:
            return None

    def _inject_mysql_hint(self, sql: str, max_ms: int) -> str:
        stripped = sql.lstrip()
        if stripped.upper().startswith("SELECT"):
            return re.sub(
                r"(?i)^SELECT\s+",
                f"SELECT /*+ MAX_EXECUTION_TIME({max_ms}) */ ",
                stripped,
                count=1,
            )
        return sql

    def _thread_timeout_execute(
        self, engine: Engine, sql: str, params: Optional[dict], *, fetch: str
    ) -> Any | None:
        def _run():
            with engine.connect() as conn:
                result = conn.execute(text(sql), params or {})
                if fetch == "one":
                    return result.fetchone()
                return result.fetchall()

        if self._pool is None:
            self._pool = concurrent.futures.ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="sql-timeout"
            )
        future = self._pool.submit(_run)
        try:
            return future.result(timeout=self.timeout_sec)
        except (concurrent.futures.TimeoutError, Exception):
            future.cancel()
            return None

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
