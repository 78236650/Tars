"""SQLite busy/locked retry (P1 #5)."""
import sqlite3

import pytest

from tars.database.sqlite_retry import is_sqlite_locked_error, run_sqlite_with_retry


def test_is_sqlite_locked_error():
    assert is_sqlite_locked_error(sqlite3.OperationalError("database is locked"))
    assert is_sqlite_locked_error(sqlite3.OperationalError("database is busy"))
    assert not is_sqlite_locked_error(sqlite3.OperationalError("no such table"))


def test_run_sqlite_with_retry_succeeds_on_second_attempt():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] == 1:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    assert run_sqlite_with_retry(fn, attempts=4, base_delay_sec=0) == "ok"
    assert calls["n"] == 2


def test_run_sqlite_with_retry_raises_after_exhausted():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise sqlite3.OperationalError("database is locked")

    with pytest.raises(sqlite3.OperationalError):
        run_sqlite_with_retry(fn, attempts=3, base_delay_sec=0)
    assert calls["n"] == 3
