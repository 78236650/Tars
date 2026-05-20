"""Metric SQL table identifier quoting (P1 #4)."""
import pytest

from tars.insight.sql_quoting import apply_tables_quoting


def test_apply_tables_quoting_postgresql_reserved():
    sql = "SELECT SUM(amount) AS value FROM order WHERE dt = '{{as_of_date}}'"
    out = apply_tables_quoting(sql, ["order"], "postgresql")
    assert '"order"' in out
    assert " FROM order " not in out


def test_apply_tables_quoting_mysql_backticks():
    sql = "SELECT COUNT(*) AS value FROM my table"
    out = apply_tables_quoting(sql, ["my table"], "mysql")
    assert "`my table`" in out


def test_apply_tables_quoting_schema_qualified():
    sql = "SELECT 1 FROM dbo.orders o"
    out = apply_tables_quoting(sql, ["dbo.orders"], "postgresql")
    assert '"dbo"."orders"' in out


def test_apply_tables_quoting_skips_already_quoted():
    sql = 'SELECT 1 FROM "orders"'
    out = apply_tables_quoting(sql, ["orders"], "postgresql")
    assert out == sql


def test_apply_tables_quoting_sqlserver():
    sql = "SELECT 1 FROM order-items"
    out = apply_tables_quoting(sql, ["order-items"], "sqlserver")
    assert "[order-items]" in out
