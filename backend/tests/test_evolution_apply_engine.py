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


def test_apply_skill_description_updates_file(engine, db, tmp_path):
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("---\ndescription: old text\n---\n\nbody", encoding="utf-8")
    record = engine.apply_skill_description(
        "tenant1",
        "demo-skill",
        "improved description",
        skill_md_path=str(skill_path),
    )
    content = skill_path.read_text(encoding="utf-8")
    assert "improved description" in content
    log = db.get_evolution_apply_log(record.id)
    assert log["target_type"] == "skill_description"


def test_apply_prompt_writes_file(engine, db, tmp_path):
    record = engine.apply_prompt("tenant1", "master", "# Master prompt\n")
    log = db.get_evolution_apply_log(record.id)
    assert log["target_type"] == "prompt"
    prompt_path = tmp_path / "ws" / "tenant1" / "prompts" / "master.md"
    assert prompt_path.exists()


def test_apply_subagent_config_merges_and_audit(engine, db, tmp_path):
    record = engine.apply_subagent_config(
        "tenant1",
        {"delegation_weights": {"code": 0.4, "writing": 0.2}},
    )
    cfg_path = tmp_path / "ws" / "tenant1" / "subagents.json"
    assert cfg_path.exists()
    data = engine.read_subagent_config("tenant1")
    assert data["delegation_weights"]["code"] == 0.4

    engine.apply_subagent_config("tenant1", {"personality_weights": {"code": 0.6}})
    merged = engine.read_subagent_config("tenant1")
    assert merged["delegation_weights"]["code"] == 0.4
    assert merged["personality_weights"]["code"] == 0.6

    log = db.get_evolution_apply_log(record.id)
    assert log["target_type"] == "subagent_config"
