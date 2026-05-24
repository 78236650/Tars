"""Evolution v4.2.1 fix tests (F-06–F-10)."""
from datetime import datetime
from pathlib import Path

import pytest

from tars.database import Database
from tars.evolution.apply_engine import ApplyEngine, PromptDiffTooLarge, RollbackConflictError, TUNED_END, TUNED_START
from tars.evolution.config import load_evolution_config
from tars.evolution.eval_runner import EvalRunner
from tars.evolution.evaluator import ConversationRecord, EvaluationResult, FeedbackType
from tars.evolution.feedback_collector import FeedbackCollector
from tars.evolution.manager import EvolutionManager
from tars.evolution.workspace_migration import migrate_legacy_workspace


def test_migrate_legacy_workspace_copies_files(tmp_path, monkeypatch):
    import tars.evolution.workspace_migration as migr

    legacy = tmp_path / "legacy" / "default"
    legacy.mkdir(parents=True)
    (legacy / "SOUL.md").write_text("# old soul", encoding="utf-8")
    prompts = legacy / "prompts"
    prompts.mkdir()
    (prompts / "master.md").write_text("old prompt", encoding="utf-8")
    agents_root = tmp_path / "agents"
    monkeypatch.setattr(migr, "LEGACY_ROOT", legacy.parent)
    monkeypatch.setattr(migr, "AGENTS_ROOT", agents_root)

    migrated = migrate_legacy_workspace()
    assert len(migrated) >= 2
    assert (agents_root / "default" / "SOUL.md").exists()


def test_eval_runner_skips_missing_context_fields():
    runner = EvalRunner()
    case = {"category": "skill_route", "expected": "sql-helper"}
    assert runner.score_case(case, {}) is None
    assert runner.score_case(case, {"skill_id": "sql-helper"}) == 1.0


def test_eval_runner_uses_config_thresholds(tmp_path):
    cfg = tmp_path / "evolution.yaml"
    cfg.write_text("eval_gate:\n  improve_min: 0.20\n  regress_max: -0.10\n", encoding="utf-8")
    from tars.evolution import config as evo_config

    evo_config._evolution_config = load_evolution_config(cfg)
    runner = EvalRunner()
    result = runner.compare({"score": 0.5}, {"score": 0.55})
    assert result["should_rollback"] is False
    evo_config._evolution_config = None


def test_apply_prompt_uses_tuned_marker_block(tmp_path):
    db = Database(":memory:")
    engine = ApplyEngine(db, workspace_base=str(tmp_path / "agents"))
    engine.begin_batch()
    record = engine.apply_prompt("default", "master", "Be concise and cite sources.")
    content = Path(record.target_path).read_text(encoding="utf-8")
    assert TUNED_START in content
    assert TUNED_END in content
    assert "Be concise" in content


def test_apply_prompt_rejects_oversized_block(tmp_path):
    db = Database(":memory:")
    engine = ApplyEngine(db, workspace_base=str(tmp_path / "agents"))
    with pytest.raises(PromptDiffTooLarge):
        engine.apply_prompt("default", "master", "x" * 900)


def test_rollback_detects_external_modification(tmp_path):
    db = Database(":memory:")
    engine = ApplyEngine(db, workspace_base=str(tmp_path / "agents"))
    engine.begin_batch()
    record = engine.apply_personality("default", {"humor": 0.2})
    soul_path = Path(record.target_path)
    soul_path.write_text(soul_path.read_text(encoding="utf-8") + "\n# manual edit", encoding="utf-8")
    with pytest.raises(RollbackConflictError):
        engine.rollback(record.id)


def test_rollback_batch_unwinds_all_records(tmp_path):
    db = Database(":memory:")
    engine = ApplyEngine(db, workspace_base=str(tmp_path / "agents"))
    batch_id = engine.begin_batch()
    r1 = engine.apply_personality("default", {"humor": 0.2})
    r2 = engine.apply_subagent_config("default", {"delegation_weights": {"code": 1.0}})
    rolled = engine.rollback_batch(batch_id)
    assert set(rolled) == {r1.id, r2.id}


def test_orchestrator_insight_burst_bypasses_min_events(test_db, tmp_path):
    collector = FeedbackCollector(test_db)
    for i in range(3):
        collector.record_insight_feedback("default", "u1", f"log-{i}", -1, metric_key="gmv")
    mgr = EvolutionManager(db=test_db, data_dir=tmp_path / "evo")
    mgr._apply_engine.workspace_base = tmp_path / "ws"  # type: ignore[union-attr]
    for i in range(25):
        mgr.evaluator.add_conversation_record(
            ConversationRecord(
                conversation_id=f"c{i}",
                query="q",
                response="a",
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
                context={"tools_used": ["shell"], "skill_id": "sql-helper"},
            )
        )
    result = mgr.optimize(tenant_id="default")
    assert result.get("skipped") is not True
    assert result.get("insight_burst")


def test_ingest_turn_accepts_skill_id(test_db, tmp_path):
    mgr = EvolutionManager(db=test_db, data_dir=tmp_path / "evo")
    mgr._optimize_interval = 1000
    mgr.ingest_turn("t1", "u1", "s1", "q", "a", skill_id="sql-helper")
    assert mgr.evaluator.history[-1].context.get("skill_id") == "sql-helper"
