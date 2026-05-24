"""Evolution orchestrator integration tests."""
from tars.database import Database
from tars.evolution.evaluator import ConversationRecord, EvaluationResult, FeedbackType
from tars.evolution.manager import EvolutionManager


def test_manager_uses_apply_engine_for_personality(tmp_path):
    db = Database(":memory:")
    mgr = EvolutionManager(db=db, data_dir=tmp_path / "evo")
    mgr._apply_engine.workspace_base = tmp_path / "ws"  # type: ignore[union-attr]

    mgr._apply_personality_update({"honesty": 0.88})
    params = mgr._apply_engine.read_personality_params("default")  # type: ignore[union-attr]
    assert abs(params["honesty"] - 0.88) < 0.01


def test_orchestrator_skips_when_insufficient_events(tmp_path):
    db = Database(":memory:")
    mgr = EvolutionManager(db=db, data_dir=tmp_path / "evo")
    result = mgr.optimize(tenant_id="default")
    assert result.get("skipped") is True
