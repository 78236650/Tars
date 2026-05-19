"""Verify replace_draft_metrics tolerates approved-metric UNIQUE collisions."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from tars.database import Database
from tars.insight.store import InsightMetricStore


@pytest.fixture
def store(tmp_path):
    db = Database(db_path=str(tmp_path / "ins.db"))
    return InsightMetricStore(db)


def _seed_approved(store, datasource_id, tenant_id, metric_key):
    """Manually insert an approved metric so it collides on UNIQUE."""
    conn = store.db._get_conn()
    cur = conn.cursor()
    now = store._now()
    cur.execute(
        """
        INSERT INTO insight_metrics (
            id, datasource_id, tenant_id, metric_key, display_name, definition,
            sql_template, tables_json, status, source, confidence, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, '', '[]', 'approved', 'profile', 0.9, ?, ?)
        """,
        (str(uuid.uuid4()), datasource_id, tenant_id, metric_key, metric_key, "approved metric", now, now),
    )
    conn.commit()


def test_collision_with_approved_skips_candidate(store):
    _seed_approved(store, "ds1", "t1", "gmv")

    outcome = store.replace_draft_metrics(
        "ds1",
        "t1",
        [
            {"key": "gmv", "display_name": "GMV new", "definition": "..."},
            {"key": "uv", "display_name": "UV", "definition": "..."},
        ],
    )

    assert outcome["inserted"] == 1
    assert "gmv" in outcome["skipped"]
    assert "uv" not in outcome["skipped"]

    # Approved row must remain
    rows = store.list_by_datasource("ds1", "t1")
    by_key = {m.metric_key: m for m in rows}
    assert by_key["gmv"].status == "approved"
    assert by_key["uv"].status == "draft"


def test_no_collision_all_inserted(store):
    outcome = store.replace_draft_metrics(
        "ds2",
        "t1",
        [
            {"key": "a", "display_name": "A", "definition": ""},
            {"key": "b", "display_name": "B", "definition": ""},
        ],
    )
    assert outcome["inserted"] == 2
    assert outcome["skipped"] == []
