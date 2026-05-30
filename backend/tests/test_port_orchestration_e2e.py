"""港航调度端到端集成测."""
import asyncio

from tars.database.base import Database
from tars.orchestration.multi_agent_orchestrator import MultiAgentOrchestrator, decompose_goal


def test_decompose_cosco123():
    subs = decompose_goal("安排COSCO123靠3号泊位卸800箱")
    types = {s["agent_type"] for s in subs}
    assert "berth" in types
    assert "yard" in types
    yard = next(s for s in subs if s["agent_type"] == "yard")
    assert yard.get("phase") == "serial"


def test_orchestrate_cosco123_e2e():
    db = Database(":memory:")
    orch = MultiAgentOrchestrator(db=db, tenant_id="default")
    result = asyncio.run(orch.orchestrate(
        session_id="sess-e2e",
        goal="安排COSCO123靠3号泊位卸800箱",
    ))
    assert result["status"] == "done"
    assert result["task_id"]
    outputs = result["outputs"]
    agent_types = {o["agent_type"] for o in outputs}
    assert "berth" in agent_types
    assert "yard" in agent_types
    assert "shared" in result
    assert "subtasks" in result
