"""EvolutionOrchestrator batch apply tests."""
from datetime import datetime

import pytest

from tars.database import Database
from tars.evolution.evaluator import ConversationRecord, EvaluationResult, FeedbackType
from tars.evolution.feedback_collector import FeedbackCollector
from tars.evolution.manager import EvolutionManager


@pytest.fixture
def db():
    return Database(":memory:")


def _seed_events(db, tenant_id: str, count: int = 25):
    collector = FeedbackCollector(db)
    for i in range(count):
        collector.record_tool_result(tenant_id, "u1", "shell", success=(i % 3 != 0))


def test_orchestrator_runs_skill_suggestions_when_enough_events(db, tmp_path):
    tenant = "default"
    _seed_events(db, tenant, 25)
    conn = db._get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS skill_usage (
            skill_id TEXT PRIMARY KEY,
            total_calls INTEGER NOT NULL DEFAULT 0,
            last_called REAL NOT NULL DEFAULT 0.0,
            state TEXT NOT NULL DEFAULT 'active',
            success_count INTEGER NOT NULL DEFAULT 0,
            fail_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        "INSERT INTO skill_usage VALUES (?, ?, ?, ?, ?, ?)",
        ("bad-skill", 12, 0.0, "active", 1, 9),
    )
    conn.commit()

    mgr = EvolutionManager(db=db, data_dir=tmp_path / "evo")
    mgr._apply_engine.workspace_base = tmp_path / "ws"  # type: ignore[union-attr]

    for i in range(25):
        mgr.evaluator.add_conversation_record(
            ConversationRecord(
                conversation_id=f"c{i}",
                query=f"q{i}",
                response=f"a{i}",
                timestamp=datetime.now(),
                evaluation=EvaluationResult(
                    overall_score=0.6,
                    relevance=0.6,
                    completeness=0.6,
                    accuracy=0.6,
                    style_match=0.6,
                    tool_efficiency=0.6,
                    feedback_type=FeedbackType.IMPLICIT,
                ),
                context={"tools_used": ["shell"]},
            )
        )

    result = mgr.optimize(tenant_id=tenant)
    assert result.get("skipped") is not True
    assert "skill_suggestions" in result
    assert result["skill_suggestions"]
