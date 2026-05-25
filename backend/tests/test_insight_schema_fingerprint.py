"""Tests for schema fingerprinting."""
from tars.insight.schema_fingerprint import fingerprint_schema, fingerprint_table


def test_fingerprint_stable_for_same_schema():
    schema = {
        "tables": {
            "orders": {
                "columns": [
                    {"name": "id", "type": "INT", "nullable": False},
                    {"name": "amount", "type": "DECIMAL", "nullable": True},
                ],
                "primary_key": ["id"],
            }
        }
    }
    assert fingerprint_schema(schema) == fingerprint_schema(schema)


def test_fingerprint_changes_when_column_added():
    base = {
        "columns": [{"name": "id", "type": "INT", "nullable": False}],
        "primary_key": ["id"],
    }
    fp1 = fingerprint_table(base)
    extended = {
        "columns": [
            {"name": "id", "type": "INT", "nullable": False},
            {"name": "extra", "type": "TEXT", "nullable": True},
        ],
        "primary_key": ["id"],
    }
    assert fingerprint_table(extended) != fp1


def test_fingerprint_changes_when_column_type_changed():
    t1 = {
        "columns": [{"name": "id", "type": "INT", "nullable": False}],
        "primary_key": ["id"],
    }
    t2 = {
        "columns": [{"name": "id", "type": "BIGINT", "nullable": False}],
        "primary_key": ["id"],
    }
    assert fingerprint_table(t1) != fingerprint_table(t2)


def test_fingerprint_ignores_column_comment():
    t1 = {
        "columns": [{"name": "id", "type": "INT", "nullable": False, "comment": "a"}],
        "primary_key": ["id"],
    }
    t2 = {
        "columns": [{"name": "id", "type": "INT", "nullable": False, "comment": "b"}],
        "primary_key": ["id"],
    }
    assert fingerprint_table(t1) == fingerprint_table(t2)


def test_fingerprint_ignores_column_order():
    t1 = {
        "columns": [
            {"name": "a", "type": "INT", "nullable": False},
            {"name": "b", "type": "TEXT", "nullable": True},
        ],
        "primary_key": [],
    }
    t2 = {
        "columns": [
            {"name": "b", "type": "TEXT", "nullable": True},
            {"name": "a", "type": "INT", "nullable": False},
        ],
        "primary_key": [],
    }
    assert fingerprint_table(t1) == fingerprint_table(t2)


def test_fingerprint_includes_primary_key():
    t1 = {
        "columns": [{"name": "id", "type": "INT", "nullable": False}],
        "primary_key": ["id"],
    }
    t2 = {
        "columns": [{"name": "id", "type": "INT", "nullable": False}],
        "primary_key": [],
    }
    assert fingerprint_table(t1) != fingerprint_table(t2)
