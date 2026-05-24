"""Evolution FeedbackCollector tests."""
import pytest

from tars.database import Database
from tars.evolution.feedback_collector import FeedbackCollector
from tars.evolution.models import EvolutionEvent


@pytest.fixture
def db():
    return Database(":memory:")


@pytest.fixture
def collector(db):
    return FeedbackCollector(db)


def test_feedback_collector_persists_event(collector, db):
    collector.record(
        EvolutionEvent(
            tenant_id="t1",
            user_id="u1",
            source="implicit",
            signal="tool_fail",
            payload={"tool": "shell"},
            weight=1.0,
        )
    )
    rows = db.list_evolution_events(tenant_id="t1", limit=1)
    assert rows
    assert rows[0]["signal"] == "tool_fail"


def test_explicit_thumbs_down_weight(collector, db):
    collector.record_explicit_feedback("t1", "u1", "conv1", "down")
    rows = db.list_evolution_events(tenant_id="t1", limit=1)
    assert rows[0]["signal"] == "thumbs_down"
    assert rows[0]["weight"] == 2.0


def test_insight_downvote(collector, db):
    collector.record_insight_feedback("t1", "u1", "log1", -1, metric_key="gmv")
    rows = db.list_evolution_events(tenant_id="t1", limit=1)
    assert rows[0]["source"] == "insight"
    assert rows[0]["signal"] == "metric_downvote"
