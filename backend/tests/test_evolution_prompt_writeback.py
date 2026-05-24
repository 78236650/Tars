"""Prompt writeback: PromptTuner → ApplyEngine → tenant workspace."""
from datetime import datetime
from pathlib import Path

import pytest

from tars.database import Database
from tars.evolution.apply_engine import ApplyEngine
from tars.evolution.evaluator import ConversationRecord, EvaluationResult, FeedbackType
from tars.evolution.feedback_collector import FeedbackCollector
from tars.evolution.manager import EvolutionManager
from tars.evolution.orchestrator import EvolutionOrchestrator
from tars.evolution.prompt_tuner import PromptTuner


@pytest.fixture
def db():
    return Database(":memory:")


def _seed_feedback_events(db, tenant_id: str, count: int = 25):
    collector = FeedbackCollector(db)
    for i in range(count):
        collector.record_tool_result(tenant_id, "u1", "shell", success=True)


def _low_master_history(count: int = 25) -> list[ConversationRecord]:
    rows = []
    for i in range(count):
        rows.append(
            ConversationRecord(
                conversation_id=f"m{i}",
                query="explain GMV",
                response="short",
                timestamp=datetime.now(),
                evaluation=EvaluationResult(
                    overall_score=0.35,
                    relevance=0.35,
                    completeness=0.35,
                    accuracy=0.35,
                    style_match=0.35,
                    tool_efficiency=0.35,
                    feedback_type=FeedbackType.IMPLICIT,
                ),
                context={"prompt_type": "master", "tools_used": []},
            )
        )
    return rows


def test_orchestrator_writes_tuned_master_prompt_to_workspace(db, tmp_path):
    tenant = "tenant-a"
    _seed_feedback_events(db, tenant, 25)
    ws = tmp_path / "ws"
    engine = ApplyEngine(db, workspace_base=str(ws))
    tuner = PromptTuner()
    mgr = EvolutionManager(db=db, data_dir=tmp_path / "evo")
    mgr._apply_engine = engine  # type: ignore[assignment]
    mgr._orchestrator = EvolutionOrchestrator(
        db,
        feedback_collector=FeedbackCollector(db),
        apply_engine=engine,
        personality_optimizer=mgr.personality_optimizer,
        subagent_optimizer=mgr.subagent_optimizer,
        prompt_tuner=tuner,
        evaluator=mgr.evaluator,
        min_events=20,
    )
    for rec in _low_master_history(25):
        mgr.evaluator.add_conversation_record(rec)

    result = mgr.optimize(tenant_id=tenant)
    assert result.get("prompts_tuned") is True
    assert result.get("prompt_apply_records")

    master_path = ws / tenant / "prompts" / "master.md"
    assert master_path.exists()
    content = master_path.read_text(encoding="utf-8")
    assert "TARS" in content
    assert "relevant" in content.lower() or "complete" in content.lower()

    log = db.get_evolution_apply_log(result["prompt_apply_records"][0])
    assert log["target_type"] == "prompt"
    assert log["target_path"] == str(master_path)


def test_apply_prompt_roundtrip_and_rollback(db, tmp_path):
    engine = ApplyEngine(db, workspace_base=str(tmp_path / "ws"))
    v1 = "Be concise."
    engine.apply_prompt("t1", "master", v1)
    assert "Be concise" in engine.read_prompt("t1", "master")

    v2 = "Be thorough."
    record2 = engine.apply_prompt("t1", "master", v2)
    assert "thorough" in engine.read_prompt("t1", "master")

    assert engine.rollback(record2.id)
    assert "Be concise" in engine.read_prompt("t1", "master")
    assert "thorough" not in engine.read_prompt("t1", "master")


def test_orchestrator_skips_prompt_writeback_when_scores_high(db, tmp_path):
    tenant = "tenant-b"
    _seed_feedback_events(db, tenant, 25)
    ws = tmp_path / "ws"
    engine = ApplyEngine(db, workspace_base=str(ws))
    mgr = EvolutionManager(db=db, data_dir=tmp_path / "evo")
    mgr._apply_engine = engine  # type: ignore[assignment]
    mgr._orchestrator = EvolutionOrchestrator(
        db,
        feedback_collector=FeedbackCollector(db),
        apply_engine=engine,
        personality_optimizer=mgr.personality_optimizer,
        subagent_optimizer=mgr.subagent_optimizer,
        prompt_tuner=mgr.prompt_tuner,
        evaluator=mgr.evaluator,
        min_events=20,
    )

    for i in range(25):
        mgr.evaluator.add_conversation_record(
            ConversationRecord(
                conversation_id=f"h{i}",
                query="q",
                response="a",
                timestamp=datetime.now(),
                evaluation=EvaluationResult(
                    overall_score=0.95,
                    relevance=0.95,
                    completeness=0.95,
                    accuracy=0.95,
                    style_match=0.95,
                    tool_efficiency=0.95,
                    feedback_type=FeedbackType.IMPLICIT,
                ),
                context={"prompt_type": "master"},
            )
        )

    result = mgr.optimize(tenant_id=tenant)
    master_path = ws / tenant / "prompts" / "master.md"
    assert not master_path.exists()
    assert result.get("prompt_apply_records") is None
