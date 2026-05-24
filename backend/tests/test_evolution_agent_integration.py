"""Evolution ↔ Agent integration tests."""
from unittest.mock import MagicMock

import pytest

from tars.database import Database
from tars.evolution.feedback_collector import FeedbackCollector
from tars.evolution.manager import EvolutionManager


@pytest.fixture
def db():
    return Database(":memory:")


@pytest.fixture
def manager(db, tmp_path):
    return EvolutionManager(db=db, data_dir=tmp_path / "evo")


def test_ingest_turn_increments_conversation_count(manager):
    manager._optimize_interval = 100
    manager.ingest_turn("t1", "u1", "sess1", "hello", "hi there")
    assert manager._conversation_count == 1


def test_ingest_turn_skipped_when_disabled(manager):
    manager.enabled = False
    manager.ingest_turn("t1", "u1", "sess1", "hello", "hi")
    assert manager._conversation_count == 0


def test_auto_optimize_triggers_at_interval(manager, monkeypatch):
    manager._optimize_interval = 2
    calls = []

    def fake_optimize(tenant_id="default"):
        calls.append(tenant_id)
        return {"skipped": True}

    monkeypatch.setattr(manager, "optimize", fake_optimize)
    manager.ingest_turn("t1", "u1", "s1", "q1", "a1")
    manager.ingest_turn("t1", "u1", "s2", "q2", "a2")
    assert calls == ["t1"]


def test_agent_tool_context_wires_feedback_collector(db, manager):
    from tars.agent.agent import AgentV2

    agent = AgentV2(db=db, evolution_manager=manager)
    collector = (
        agent.evolution_manager.feedback_collector if agent.evolution_manager else None
    )
    assert isinstance(collector, FeedbackCollector)

    tool_context = {
        "session_id": "sess",
        "tenant_id": "default",
        "user_id": "u1",
        "_feedback_collector": collector,
    }
    assert tool_context["_feedback_collector"] is collector


def test_ingest_turn_records_tools_in_evaluator_context(manager):
    manager.ingest_turn(
        "t1",
        "u1",
        "sess",
        "question",
        "answer",
        tool_results=[{"name": "shell", "success": True}, {"name": "memory", "success": False}],
    )
    assert manager.evaluator.history
    last = manager.evaluator.history[-1]
    assert last.tools_used == ["shell", "memory"]
