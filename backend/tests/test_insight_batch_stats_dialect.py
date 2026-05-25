"""Tests for batch column stats SQL."""
from tars.insight.dialects.batch_stats import (
    build_batch_stats_sql,
    parse_batch_result,
    split_column_batches,
)


def test_batch_mysql_sql_shape():
    sql = build_batch_stats_sql("orders", ["id", "amount", "status"], "mysql")
    assert "COUNT(*)" in sql
    assert "COUNT(DISTINCT" in sql
    assert "`amount`" in sql
    assert len(sql) < 8000


def test_batch_sqlite_sql_shape():
    sql = build_batch_stats_sql("orders", ["id", "amount", "status"], "sqlite")
    assert "COUNT(*)" in sql
    assert "COUNT(DISTINCT" in sql


def test_batch_respects_max_size():
    cols = [f"col_{i}" for i in range(30)]
    batches = split_column_batches(cols, 10)
    assert len(batches) == 3
    assert all(len(b) <= 10 for b in batches)


def test_parse_batch_result():
    row = (100, 5, 90, 2, 80)
    parsed = parse_batch_result(row, ["a", "b"])
    assert parsed["a"]["null_rate"] == 0.05
    assert parsed["a"]["distinct_count"] == 90
    assert parsed["b"]["distinct_count"] == 80
