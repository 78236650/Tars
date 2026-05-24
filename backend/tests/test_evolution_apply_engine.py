"""Evolution ApplyEngine tests."""
import pytest

from tars.database import Database
from tars.evolution.apply_engine import ApplyEngine


@pytest.fixture
def db():
    return Database(":memory:")


@pytest.fixture
def engine(db, tmp_path):
    return ApplyEngine(db, workspace_base=str(tmp_path / "ws"))


def test_apply_personality_updates_soul_and_audit(engine, db):
    record = engine.apply_personality("tenant1", {"honesty": 0.95, "humor": 0.2})
    params = engine.read_personality_params("tenant1")
    assert abs(params["honesty"] - 0.95) < 0.01
    assert abs(params["humor"] - 0.2) < 0.01
    log = db.get_evolution_apply_log(record.id)
    assert log is not None
    assert log["target_type"] == "personality"


def test_rollback_restores_soul(engine):
    baseline = engine.read_personality_params("tenant1")
    record = engine.apply_personality("tenant1", {"honesty": 0.99})
    assert engine.read_personality_params("tenant1")["honesty"] > 0.9
    assert engine.rollback(record.id)
    restored = engine.read_personality_params("tenant1")
    assert abs(restored["honesty"] - baseline["honesty"]) < 0.01
