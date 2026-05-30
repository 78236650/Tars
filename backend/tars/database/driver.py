"""Database driver abstraction — SQLite default, Postgres via DATABASE_URL."""

from __future__ import annotations

import os
import re
import sqlite3
from typing import Any, Optional, Sequence, Tuple, Union

Params = Optional[Union[Sequence[Any], Tuple[Any, ...]]]


def default_sqlite_path() -> str:
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
    )
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "tars.db")


def parse_database_url(db_path: Optional[str] = None) -> str:
    """Resolve database URL or SQLite file path from env or explicit override."""
    if db_path:
        return db_path
    return (
        os.environ.get("DATABASE_URL")
        or os.environ.get("TARS_DATABASE_URL")
        or default_sqlite_path()
    )


def detect_dialect(url: str) -> str:
    if url.startswith(("postgresql://", "postgres://")):
        return "postgres"
    return "sqlite"


def adapt_sql(sql: str, dialect: str) -> str:
    if dialect != "postgres":
        return sql
    if sql.strip().upper().startswith("PRAGMA"):
        return sql
    return sql.replace("?", "%s")


class _NoOpCursor:
    """Stand-in cursor for PRAGMA no-ops on Postgres."""

    description = None
    rowcount = 0

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def fetchmany(self, size=None):
        return []


class DbCursor:
    """Wraps sqlite3/psycopg2 cursors; converts ``?`` placeholders on Postgres."""

    def __init__(self, raw_cursor, dialect: str):
        self._cursor = raw_cursor
        self._dialect = dialect
        self._lastrowid: Optional[int] = None
        self._noop = False

    @property
    def description(self):
        if self._noop:
            return None
        return self._cursor.description

    @property
    def rowcount(self) -> int:
        if self._noop:
            return 0
        return self._cursor.rowcount

    @property
    def lastrowid(self) -> Optional[int]:
        if self._noop:
            return None
        if self._dialect == "sqlite":
            return self._cursor.lastrowid
        if self._lastrowid is not None:
            return self._lastrowid
        try:
            self._cursor.execute("SELECT lastval()")
            row = self._cursor.fetchone()
            if row:
                self._lastrowid = int(row[0])
                return self._lastrowid
        except Exception:
            pass
        return None

    def execute(self, sql: str, params: Params = None) -> "DbCursor":
        adapted = adapt_sql(sql, self._dialect)
        if self._dialect == "postgres" and adapted.strip().upper().startswith("PRAGMA"):
            self._noop = True
            return self
        self._noop = False
        if params is None:
            self._cursor.execute(adapted)
        else:
            self._cursor.execute(adapted, params)
        if self._dialect == "postgres" and adapted.strip().upper().startswith("INSERT"):
            m = re.search(r"\bRETURNING\b", adapted, re.IGNORECASE)
            if m:
                row = self._cursor.fetchone()
                if row:
                    self._lastrowid = int(row[0])
        return self

    def executemany(self, sql: str, params_seq) -> "DbCursor":
        adapted = adapt_sql(sql, self._dialect)
        self._cursor.executemany(adapted, params_seq)
        return self

    def fetchone(self):
        if self._noop:
            return None
        return self._cursor.fetchone()

    def fetchall(self):
        if self._noop:
            return []
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        if self._noop:
            return []
        if size is None:
            return self._cursor.fetchmany()
        return self._cursor.fetchmany(size)

    def close(self):
        if not self._noop:
            self._cursor.close()


class DbConnection:
    """Unified connection wrapper for SQLite and Postgres."""

    def __init__(self, raw_conn, dialect: str, factory: "ConnectionFactoryBase"):
        self._conn = raw_conn
        self.dialect = dialect
        self._factory = factory

    def cursor(self) -> DbCursor:
        return DbCursor(self._conn.cursor(), self.dialect)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def execute(self, sql: str, params: Params = None) -> DbCursor:
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def close(self) -> None:
        self._factory.release(self)


class ConnectionFactoryBase:
    def get_conn(self) -> DbConnection:
        raise NotImplementedError

    def release(self, conn: DbConnection) -> None:
        raise NotImplementedError


class SqliteConnectionFactory(ConnectionFactoryBase):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._raw: Optional[sqlite3.Connection] = None
        self._wrapper: Optional[DbConnection] = None

    def get_conn(self) -> DbConnection:
        if self._wrapper is None:
            busy_ms = int(os.environ.get("TARS_SQLITE_BUSY_MS", "15000"))
            self._raw = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=busy_ms / 1000.0,
            )
            self._raw.execute("PRAGMA journal_mode=WAL")
            self._raw.execute("PRAGMA synchronous=NORMAL")
            self._raw.execute(f"PRAGMA busy_timeout={busy_ms}")
            self._wrapper = DbConnection(self._raw, "sqlite", self)
        return self._wrapper

    def release(self, conn: DbConnection) -> None:
        if self._raw is not None:
            self._raw.close()
            self._raw = None
            self._wrapper = None


class PostgresConnectionFactory(ConnectionFactoryBase):
    def __init__(self, database_url: str):
        import psycopg2
        from psycopg2 import pool

        max_conn = int(os.environ.get("TARS_PG_POOL_MAX", "10"))
        self._pool = pool.SimpleConnectionPool(1, max_conn, database_url)
        self._wrapper: Optional[DbConnection] = None
        self._raw = None

    def get_conn(self) -> DbConnection:
        if self._wrapper is None:
            self._raw = self._pool.getconn()
            self._raw.autocommit = False
            self._wrapper = DbConnection(self._raw, "postgres", self)
        return self._wrapper

    def release(self, conn: DbConnection) -> None:
        if self._raw is not None:
            self._pool.putconn(self._raw)
            self._raw = None
            self._wrapper = None


def create_connection_factory(url: str) -> ConnectionFactoryBase:
    dialect = detect_dialect(url)
    if dialect == "postgres":
        return PostgresConnectionFactory(url)
    return SqliteConnectionFactory(url)
