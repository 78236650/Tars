"""Insight: started_at + sweep_stuck_runs behaviors."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from tars.database import Database
from tars.insight.store import InsightProfileRunStore


@pytest.fixture
def store(tmp_path):
    db = Database(db_path=str(tmp_path / "ins.db"))
    return InsightProfileRunStore(db)


def test_started_at_written_on_first_running(store):
    run = store.create(
        datasource_id="ds1",
        tenant_id="t1",
        capability_version="INS-1.0.0",
        budget={"max_tables": 10},
    )
    assert run.started_at is None

    store.update_progress(run.id, "t1", {"phase": "schema"}, status="running")
    refreshed = store.get(run.id, "t1")
    assert refreshed is not None
    assert refreshed.started_at is not None
    first_started = refreshed.started_at

    # Idempotent: second 'running' update does NOT overwrite started_at
    store.update_progress(run.id, "t1", {"phase": "stats"}, status="running")
    again = store.get(run.id, "t1")
    assert again.started_at == first_started


def test_started_at_not_set_on_progress_without_status(store):
    run = store.create(
        datasource_id="ds1",
        tenant_id="t1",
        capability_version="INS-1.0.0",
        budget={},
    )
    store.update_progress(run.id, "t1", {"phase": "preflight"})
    refreshed = store.get(run.id, "t1")
    assert refreshed.started_at is None


def test_sweep_stuck_runs_marks_failed(store):
    run1 = store.create("ds1", "t1", "INS-1.0.0", {})
    run2 = store.create("ds2", "t1", "INS-1.0.0", {})
    store.update_progress(run1.id, "t1", {}, status="running")
    # run2 stays pending; run1 stays running

    swept = store.sweep_stuck_runs(reason="test sweep")
    assert swept >= 2

    r1 = store.get(run1.id, "t1")
    r2 = store.get(run2.id, "t1")
    assert r1.status == "failed"
    assert r1.error == "test sweep"
    assert r1.finished_at is not None
    assert r2.status == "failed"
    assert r2.error == "test sweep"


def test_sweep_skips_completed_and_failed(store):
    run = store.create("ds1", "t1", "INS-1.0.0", {})
    store.complete(run.id, "t1", status="completed", insight_snapshot={})

    swept = store.sweep_stuck_runs()
    assert swept == 0

    r = store.get(run.id, "t1")
    assert r.status == "completed"
