"""INS-2.0 database migration tests."""
import json

import pytest

from tars.database import Database
from tars.database.bi_store import DataSourceStore
from tars.insight.migrations import run_insight_ins2_migrations
from tars.insight.store import InsightProfileRunStore


def test_sessions_has_metadata_json_column():
    db = Database(":memory:")
    conn = db._get_conn()
    row = conn.execute("PRAGMA table_info(sessions)").fetchall()
    cols = {r[1] for r in row}
    assert "metadata_json" in cols


def test_insight_question_log_table_exists():
    db = Database(":memory:")
    conn = db._get_conn()
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "insight_question_log" in tables
    assert "insight_metric_adoptions" in tables


def test_insight_metrics_has_version_column():
    db = Database(":memory:")
    conn = db._get_conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(insight_metrics)").fetchall()}
    assert "version" in cols
    assert "superseded_by" in cols
    indexes = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='insight_metrics'"
    ).fetchall()
    index_names = {r[0] for r in indexes}
    assert "idx_insight_metrics_key_ver" in index_names


def test_backfill_workflow_ready_after_completed_run():
    db = Database(":memory:")
    bi = DataSourceStore(db)
    ds = bi.create("default", "ds-a", "postgresql", "postgresql://localhost/x")
    run_store = InsightProfileRunStore(db)
    run = run_store.create(ds.id, "default", "INS-2.0.0", {})
    run_store.complete(run.id, "default", insight_snapshot={"tables": 1})

    conn = db._get_conn()
    cursor = conn.cursor()
    run_insight_ins2_migrations(cursor)
    conn.commit()

    loaded = bi.get(ds.id, "default")
    workflow = (loaded.schema_snapshot or {}).get("insight", {}).get("workflow", {})
    assert workflow.get("state") == "ready"
    assert workflow.get("ins_version") == "INS-2.0.0"


def test_backfill_workflow_needs_forge_without_run():
    db = Database(":memory:")
    bi = DataSourceStore(db)
    ds = bi.create("default", "ds-b", "mysql", "mysql://localhost/y")

    conn = db._get_conn()
    cursor = conn.cursor()
    run_insight_ins2_migrations(cursor)
    conn.commit()

    loaded = bi.get(ds.id, "default")
    workflow = (loaded.schema_snapshot or {}).get("insight", {}).get("workflow", {})
    assert workflow.get("state") == "needs_forge"
