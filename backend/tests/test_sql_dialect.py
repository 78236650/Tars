"""Task 9: SQL 方言隔离测试。"""

from tars.database.sql_dialect import fulltext_match_clause


def test_sqlite_fts_clause():
    clause = fulltext_match_clause("sqlite", "col")
    assert "MATCH ?" in clause


def test_postgres_tsvector_clause():
    clause = fulltext_match_clause("postgres", "col", ":kw")
    assert "to_tsvector" in clause
    assert "plainto_tsquery" in clause
