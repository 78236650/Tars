"""Tests for SqlTimeoutExecutor."""
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from tars.insight.sql_timeout import SqlTimeoutExecutor


def test_fast_query_succeeds(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/fast.db")
    exec_ = SqlTimeoutExecutor(timeout_sec=5, dialect="sqlite")
    row = exec_.fetch_one(engine, "SELECT 1")
    assert row is not None
    assert row[0] == 1


SLOW_SQLITE_CTE = """
    WITH RECURSIVE cnt(x) AS (
      SELECT 1 UNION ALL SELECT x+1 FROM cnt WHERE x < 30000000
    ) SELECT COUNT(*) FROM cnt
"""


def test_sqlite_slow_query_returns_none(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/slow.db")
    exec_ = SqlTimeoutExecutor(timeout_sec=1, dialect="sqlite")
    t0 = time.time()
    result = exec_.fetch_one(engine, SLOW_SQLITE_CTE)
    elapsed = time.time() - t0
    if result is not None and elapsed < 1.0:
        pytest.skip("SQLite CTE completed faster than timeout on this host")
    assert result is None
    assert elapsed < 3.0
