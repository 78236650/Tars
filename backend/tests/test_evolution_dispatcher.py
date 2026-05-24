"""ToolDispatcher evolution feedback wiring."""
import pytest

from tars.database import Database
from tars.evolution.feedback_collector import FeedbackCollector
from tars.tools.base import ToolResult
from tars.tools.dispatcher import ToolDispatcher
from tars.tools.registry import ToolRegistry


@pytest.fixture
def db():
    return Database(":memory:")


@pytest.fixture
def dispatcher(db):
    reg = ToolRegistry()

    class FailTool:
        name = "fail_tool"
        description = "always fails"
        parameters_schema = {"type": "object", "properties": {}}

        async def execute(self, **kwargs):
            return ToolResult(success=False, output="", error="boom")

    reg.register(FailTool())
    return ToolDispatcher(reg)


@pytest.mark.asyncio
async def test_execute_tool_records_tool_fail(dispatcher, db):
    collector = FeedbackCollector(db)
    await dispatcher.execute_tool(
        "fail_tool",
        {},
        context={
            "tenant_id": "t1",
            "user_id": "u1",
            "session_id": "s1",
            "_feedback_collector": collector,
        },
    )
    rows = db.list_evolution_events(tenant_id="t1", limit=1)
    assert rows[0]["signal"] == "tool_fail"


@pytest.mark.asyncio
async def test_missing_tool_records_fail(dispatcher, db):
    collector = FeedbackCollector(db)
    await dispatcher.execute_tool(
        "nonexistent",
        {},
        context={"tenant_id": "t1", "user_id": "u1", "_feedback_collector": collector},
    )
    rows = db.list_evolution_events(tenant_id="t1", limit=1)
    assert rows[0]["signal"] == "tool_fail"
