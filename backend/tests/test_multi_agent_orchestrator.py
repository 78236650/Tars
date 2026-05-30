import asyncio

from tars.database.base import Database
from tars.orchestration.multi_agent_orchestrator import MultiAgentOrchestrator


def test_orchestrate_records_task():
    orch = MultiAgentOrchestrator(db=Database(":memory:"))
    result = asyncio.run(orch.orchestrate(
        session_id="s1",
        goal="安排COSCO123靠3号泊位卸货",
        subtasks=[{"agent_type": "research", "task": "查3号泊位状态"}],
    ))
    assert "task_id" in result
    assert result["status"] == "done"
