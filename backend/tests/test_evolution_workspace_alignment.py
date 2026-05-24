"""Evolution workspace alignment tests (F-01)."""
from pathlib import Path

import pytest

from tars.agent.agent import AgentV2
from tars.database import Database
from tars.evolution.apply_engine import ApplyEngine
from tars.workspace.manager import WorkspaceManager


def test_apply_engine_writes_to_agents_directory(tmp_path, monkeypatch):
    agents_home = tmp_path / "agents"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    db = Database(":memory:")
    engine = ApplyEngine(db, workspace_base=str(agents_home))

    engine.apply_personality("tenant-x", {"humor": 0.99})
    soul_path = agents_home / "tenant-x" / "SOUL.md"
    assert soul_path.exists()
    assert "humor: 0.99" in soul_path.read_text(encoding="utf-8")


def test_agent_static_prompt_loads_prompt_overlay(tmp_path, monkeypatch):
    tenant_dir = tmp_path / ".tars" / "agents" / "default"
    prompts_dir = tenant_dir / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "system.md").write_text("Evolved system guidance", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    agent = AgentV2(db=Database(":memory:"))
    prompt = agent._build_static_prompt("hello", "sess-1", None, tenant_id="default")
    assert "Evolved system guidance" in prompt


def test_subagent_manager_applies_tenant_overrides(tmp_path, monkeypatch):
    import json

    agents_home = tmp_path / ".tars" / "agents" / "default"
    agents_home.mkdir(parents=True)
    (agents_home / "subagents.json").write_text(
        json.dumps({"code": {"enabled": False}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    from tars.agent.subagent_manager import SubAgentManager
    from tars.agent.subagents.base import SubAgentType

    mgr = SubAgentManager()
    mgr.apply_tenant_overrides("default")
    assert mgr.subagents[SubAgentType.CODE].config.enabled is False


def test_subagent_manager_applies_delegation_weights(tmp_path, monkeypatch):
    import json

    agents_home = tmp_path / ".tars" / "agents" / "default"
    agents_home.mkdir(parents=True)
    (agents_home / "subagents.json").write_text(
        json.dumps({"delegation_weights": {"code": 0.1, "data": 2.0}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    from tars.agent.subagent_manager import SubAgentManager
    from tars.agent.subagents.base import SubAgentType

    mgr = SubAgentManager()
    mgr.apply_tenant_overrides("default")
    # Task mentions both code and data keywords; data has higher weight.
    chosen = mgr._determine_agent_type("analyze python data chart")
    assert chosen == SubAgentType.DATA


def test_workspace_manager_for_tenant_matches_apply_engine_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    ws = WorkspaceManager.for_tenant("acme")
    assert ws.workspace_path == tmp_path / ".tars" / "agents" / "acme"
