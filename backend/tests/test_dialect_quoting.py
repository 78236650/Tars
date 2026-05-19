"""Dialect identifier quoting tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from tars.insight.dialects.base import quote_ident, quote_table


class TestQuoteIdent:
    def test_ascii_simple(self):
        assert quote_ident("orders", "mysql") == "`orders`"
        assert quote_ident("orders", "postgresql") == '"orders"'

    def test_unicode_chinese(self):
        assert quote_ident("用户表", "mysql") == "`用户表`"

    def test_hyphen_allowed(self):
        assert quote_ident("order-items", "postgresql") == '"order-items"'

    def test_space_allowed(self):
        assert quote_ident("my table", "mysql") == "`my table`"

    def test_embedded_backtick_rejected(self):
        with pytest.raises(ValueError):
            quote_ident("bad`name", "mysql")

    def test_embedded_double_quote_rejected(self):
        with pytest.raises(ValueError):
            quote_ident('bad"name', "postgresql")

    def test_semicolon_rejected(self):
        with pytest.raises(ValueError):
            quote_ident("drop;--", "generic")

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            quote_ident("", "generic")


class TestQuoteTable:
    def test_single_part(self):
        assert quote_table("orders", "mysql") == "`orders`"

    def test_two_part(self):
        assert quote_table("mydb.orders", "postgresql") == '"mydb"."orders"'

    def test_three_part(self):
        assert quote_table("catalog.schema.table", "mysql") == "`catalog`.`schema`.`table`"

    def test_chinese_table(self):
        assert quote_table("数据库.用户表", "mysql") == "`数据库`.`用户表`"
