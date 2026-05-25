"""Tests for InsightProfileRunStore.latest_completed_for_datasource."""
import sqlite3

import pytest

from tars.database import Database
from tars.insight.store import InsightProfileRunStore


@pytest.fixture
def insight_db(tmp_path):
    db_path = tmp_path / "runs.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE insight_profile_runs (
            id TEXT PRIMARY KEY,
            datasource_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            capability_version TEXT NOT NULL,
            status TEXT NOT NULL,
            budget_json TEXT NOT NULL,
            progress_json TEXT NOT NULL DEFAULT '{}',
            insight_snapshot_json TEXT,
            knowledge_doc_id TEXT,
            error TEXT,
            started_at TEXT,
            finished_at TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()
    return Database(str(db_path))


def test_latest_completed_excludes_pending_failed(insight_db):
    store = InsightProfileRunStore(insight_db)
    r1 = store.create("ds1", "default", "INS-2.1.0", {})
    store.complete(r1.id, "default", status="failed")
    r2 = store.create("ds1", "default", "INS-2.1.0", {})
    store.complete(
        r2.id,
        "default",
        status="completed",
        insight_snapshot={"tables": {"t1": {}}},
    )
    latest = store.latest_completed_for_datasource("ds1", "default")
    assert latest.id == r2.id
    assert latest.insight_snapshot_json["tables"] == {"t1": {}}


def test_latest_completed_returns_none_when_no_completed(insight_db):
    store = InsightProfileRunStore(insight_db)
    store.create("ds2", "default", "INS-2.1.0", {})
    assert store.latest_completed_for_datasource("ds2") is None
