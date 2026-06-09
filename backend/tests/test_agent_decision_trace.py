"""Unit tests for agent decision tracing (v5.0.5/A6)."""

import pytest

from tars.agent.decision_trace import (
    KB_PROMOTE,
    MEMORY_RETRIEVE,
    SKILL_ROUTE,
    query_decisions,
    record_decision,
)
from tars.context import set_trace_id
from tars.database.base import Database
from tars.database.migrations import apply_migrations


@pytest.fixture
def db():
    d = Database(":memory:")
    apply_migrations(d._get_conn())
    yield d
    d.close()


def test_record_and_query_roundtrip(db):
    decision_id = record_decision(
        db,
        decision_type=SKILL_ROUTE,
        session_id="s1",
        decision_input={"query": "查泊位"},
        decision_output={"skill": "berth_lookup"},
        reasoning="匹配到泊位技能",
    )
    assert decision_id

    rows = query_decisions(db, session_id="s1")
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == decision_id
    assert row["decision_type"] == SKILL_ROUTE
    # dict inputs are JSON-serialized on the way in
    assert "berth_lookup" in row["decision_output"]
    assert row["reasoning"] == "匹配到泊位技能"


def test_trace_id_captured_from_context(db):
    set_trace_id("trace-xyz")
    try:
        record_decision(db, decision_type=MEMORY_RETRIEVE, session_id="s2")
    finally:
        set_trace_id("")
    rows = query_decisions(db, trace_id="trace-xyz")
    assert len(rows) == 1
    assert rows[0]["trace_id"] == "trace-xyz"


def test_query_filters_by_decision_type(db):
    record_decision(db, decision_type=SKILL_ROUTE, session_id="s3")
    record_decision(db, decision_type=MEMORY_RETRIEVE, session_id="s3")
    record_decision(db, decision_type=KB_PROMOTE, session_id="s3")

    assert len(query_decisions(db, session_id="s3")) == 3
    only_route = query_decisions(db, session_id="s3", decision_type=SKILL_ROUTE)
    assert len(only_route) == 1
    assert only_route[0]["decision_type"] == SKILL_ROUTE


def test_string_input_passed_through(db):
    record_decision(
        db,
        decision_type=SKILL_ROUTE,
        session_id="s4",
        decision_input="raw string",
    )
    rows = query_decisions(db, session_id="s4")
    assert rows[0]["decision_input"] == "raw string"


def test_query_ordered_by_created_at_asc(db):
    for i in range(3):
        record_decision(
            db, decision_type=SKILL_ROUTE, session_id="s5", reasoning=f"step{i}"
        )
    rows = query_decisions(db, session_id="s5")
    assert [r["reasoning"] for r in rows] == ["step0", "step1", "step2"]


def test_query_returns_empty_for_unknown_session(db):
    assert query_decisions(db, session_id="nope") == []
