"""SQLite lock/busy retry helpers (P1 #5)."""
from __future__ import annotations

import sqlite3
import time
from typing import Callable, TypeVar

T = TypeVar("T")


def is_sqlite_locked_error(exc: BaseException) -> bool:
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    msg = str(exc).lower()
    return "database is locked" in msg or "database is busy" in msg or "locked" in msg


def run_sqlite_with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 6,
    base_delay_sec: float = 0.05,
) -> T:
    """Retry write transactions that hit SQLITE_BUSY / database is locked."""
    last: sqlite3.OperationalError | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            if not is_sqlite_locked_error(e):
                raise
            last = e
            if attempt + 1 >= attempts:
                break
            time.sleep(base_delay_sec * (2**attempt))
    assert last is not None
    raise last
