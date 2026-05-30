"""Postgres connection layer tests (optional integration via TARS_TEST_DATABASE_URL)."""

import os

import pytest

from tars.database.base import Database
from tars.database.driver import (
    DbCursor,
    detect_dialect,
    parse_database_url,
    adapt_sql,
)
from tars.database.sql_dialect import fulltext_match_clause, insert_upsert, placeholder


class TestDriverUnit:
    def test_parse_database_url_default_is_sqlite_path(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("TARS_DATABASE_URL", raising=False)
        url = parse_database_url()
        assert detect_dialect(url) == "sqlite"
        assert url.endswith("tars.db")

    def test_parse_database_url_explicit_override(self):
        assert parse_database_url(":memory:") == ":memory:"
        assert detect_dialect("postgresql://u:p@localhost/tars") == "postgres"

    def test_placeholder_conversion_sqlite(self):
        assert adapt_sql("SELECT * FROM t WHERE id = ?", "sqlite") == "SELECT * FROM t WHERE id = ?"

    def test_placeholder_conversion_postgres(self):
        assert adapt_sql("SELECT * FROM t WHERE id = ?", "postgres") == "SELECT * FROM t WHERE id = %s"

    def test_db_cursor_execute_converts_placeholders(self):
        cur = DbCursor(_FakeCursor(), "postgres")
        cur.execute("INSERT INTO t VALUES (?, ?)", (1, "a"))
        assert cur._cursor.last_sql == "INSERT INTO t VALUES (%s, %s)"
        assert cur._cursor.last_params == (1, "a")

    def test_sql_dialect_placeholder(self):
        assert placeholder("sqlite") == "?"
        assert placeholder("postgres") == "%s"

    def test_insert_upsert_sqlite(self):
        sql = insert_upsert("sqlite", "items", ["id", "name"], conflict_cols=["id"])
        assert "INSERT OR IGNORE" in sql

    def test_insert_upsert_postgres(self):
        sql = insert_upsert("postgres", "items", ["id", "name"], conflict_cols=["id"])
        assert "ON CONFLICT (id)" in sql
        assert "%s" in sql

    def test_postgres_fulltext_default_placeholder(self):
        clause = fulltext_match_clause("postgres", "content")
        assert "%s" in clause
        assert ":kw" not in clause

    def test_memory_repo_like_op_postgres(self):
        from tars.database.repositories.memory_repo import MemoryRepo

        class _CM:
            dialect = "postgres"

        assert MemoryRepo(_CM())._like_op() == "ILIKE"

    def test_memory_repo_like_op_sqlite(self):
        from tars.database.repositories.memory_repo import MemoryRepo

        class _CM:
            dialect = "sqlite"

        assert MemoryRepo(_CM())._like_op() == "LIKE"

    def test_fulltext_match_clause_with_explicit_placeholder(self):
        clause = fulltext_match_clause("postgres", "m.content", "%s")
        assert "plainto_tsquery('simple', %s)" in clause
        clause_sqlite = fulltext_match_clause("sqlite", "fts", "?")
        assert clause_sqlite == "fts MATCH ?"


class _FakeCursor:
    def __init__(self):
        self.last_sql = None
        self.last_params = None

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.last_params = params

    def fetchone(self):
        return None

    def fetchall(self):
        return []


@pytest.mark.skipif(
    not os.environ.get("TARS_TEST_DATABASE_URL"),
    reason="TARS_TEST_DATABASE_URL not set — sqlite-only driver tests run",
)
class TestPostgresIntegration:
    def test_database_init_and_create_session(self):
        db = Database(os.environ["TARS_TEST_DATABASE_URL"])
        try:
            session = db.create_session(user_id="pg-user", title="PG smoke")
            assert session.id
            assert session.user_id == "pg-user"
            assert session.title == "PG smoke"
        finally:
            db.close()

    def test_search_memories_postgres_no_fts_table(self):
        """PG has no memories_fts; search_memories must not raise."""
        from tars.context import clear_request_context, set_request_context

        db = Database(os.environ["TARS_TEST_DATABASE_URL"])
        try:
            set_request_context("pg-search-user")
            db.add_memory(
                content="Postgres dialect search smoke test",
                category="fact",
                scope="private",
                tenant_id="org_default",
                user_id="pg-search-user",
            )
            results = db.search_memories(
                "Postgres dialect",
                tenant_id="org_default",
                user_id="pg-search-user",
            )
            assert any("Postgres dialect search" in m.content for m in results)
        finally:
            clear_request_context()
            db.close()
