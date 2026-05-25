"""Tests for BI SQL security checker."""
from tars.bi.security import SQLSecurityChecker


class TestSQLSecurityChecker:
    def setup_method(self):
        self.checker = SQLSecurityChecker(max_rows=1000)

    def test_show_tables_allowed_without_limit(self):
        valid, err = self.checker.validate("SHOW TABLES")
        assert valid is True
        assert err == ""

        safe_sql, err = self.checker.sanitize("SHOW TABLES")
        assert err == ""
        assert safe_sql.upper() == "SHOW TABLES"

    def test_describe_allowed_without_limit(self):
        safe_sql, err = self.checker.sanitize("DESCRIBE orders")
        assert err == ""
        assert "LIMIT" not in safe_sql.upper()

    def test_select_gets_limit(self):
        safe_sql, err = self.checker.sanitize("SELECT * FROM orders")
        assert err == ""
        assert safe_sql.upper().endswith("LIMIT 1000")

    def test_insert_blocked(self):
        valid, err = self.checker.validate("INSERT INTO orders VALUES (1)")
        assert valid is False
        assert err

    def test_unknown_statement_blocked(self):
        valid, err = self.checker.validate("SET NAMES utf8mb4")
        assert valid is False
        assert "不支持" in err
