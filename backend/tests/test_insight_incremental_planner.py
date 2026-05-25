"""Tests for incremental profile planner."""
from datetime import datetime, timedelta, timezone

from tars.insight.config import InsightBudget
from tars.insight.incremental_planner import IncrementalPlanner
from tars.insight.schema_fingerprint import fingerprint_schema


def _schema(n: int) -> dict:
    return {
        "tables": {
            f"t_{i}": {"columns": [{"name": "id", "type": "INT"}], "primary_key": ["id"]}
            for i in range(n)
        }
    }


def _previous(n: int, schema: dict) -> dict:
    fps = fingerprint_schema(schema)
    return {
        "tables": {
            f"t_{i}": {"table": f"t_{i}", "columns": {"id": {"name": "id", "distinct_count": 1}}}
            for i in range(n)
        },
        "fingerprints": {f"t_{i}": fps[f"t_{i}"] for i in range(n)},
    }


def test_plan_force_full_collect():
    schema = _schema(5)
    plan = IncrementalPlanner(InsightBudget()).plan(
        schema, _previous(5, schema), force=True
    )
    assert all(a == "collect" for a in plan.actions.values())
    assert plan.profile_run_type == "full"


def test_plan_incremental_all_reuse():
    schema = _schema(5)
    plan = IncrementalPlanner(InsightBudget(enable_incremental=True)).plan(
        schema, _previous(5, schema), force=False
    )
    assert plan.reused_count == 5
    assert plan.collected_count == 0
    assert plan.profile_run_type == "incremental"


def test_plan_incremental_one_new_table():
    schema = _schema(6)
    plan = IncrementalPlanner(InsightBudget()).plan(schema, _previous(5, _schema(5)))
    assert plan.reused_count == 5
    assert plan.collected_count == 1


def test_plan_incremental_dropped_table():
    schema = _schema(4)
    plan = IncrementalPlanner(InsightBudget()).plan(schema, _previous(5, _schema(5)))
    assert plan.dropped_count == 1


def test_plan_no_previous_full():
    plan = IncrementalPlanner(InsightBudget()).plan(_schema(3), None)
    assert plan.profile_run_type == "full"
    assert plan.collected_count == 3


def test_plan_incremental_disabled():
    schema = _schema(5)
    plan = IncrementalPlanner(InsightBudget(enable_incremental=False)).plan(
        schema, _previous(5, schema)
    )
    assert all(a == "collect" for a in plan.actions.values())


def test_plan_ttl_expired_forces_collect():
    schema = _schema(3)
    completed = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    plan = IncrementalPlanner(InsightBudget(incremental_ttl_hours=24)).plan(
        schema,
        _previous(3, schema),
        previous_completed_at=completed,
    )
    assert all(a == "collect" for a in plan.actions.values())
