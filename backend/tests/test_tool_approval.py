"""Tool approval flow tests."""
import asyncio

import pytest

from tars.database import Database
from tars.security.approval_service import ApprovalService, init_approval_service
from tars.security.execution_policy import ExecutionPolicy
from tars.tools.base import BaseTool, ToolResult
from tars.tools.dispatcher import ToolDispatcher
from tars.tools.registry import ToolRegistry


class FakeCommandTool(BaseTool):
    name = "command"
    description = "run command"
    parameters_schema = {"type": "object", "properties": {"command": {"type": "string"}}}

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, output=f"ran:{kwargs.get('command', '')}")


class FakeConnectionManager:
    def __init__(self):
        self.personal = []

    async def send_personal_message(self, session_id, event):
        self.personal.append((session_id, event))
        return True


@pytest.fixture
def db():
    return Database(":memory:")


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(FakeCommandTool())
    return reg


@pytest.mark.asyncio
async def test_command_tool_creates_pending_approval_and_blocks_until_approved(db, registry):
    cm = FakeConnectionManager()
    service = ApprovalService(db, cm, timeout_seconds=5)
    init_approval_service(db, cm, timeout_seconds=5)
    import tars.security.approval_service as approval_module

    approval_module.approval_service = service

    policy = ExecutionPolicy()
    import tars.security.execution_policy as policy_module

    policy_module.execution_policy = policy

    dispatcher = ToolDispatcher(registry)
    context = {
        "session_id": "sess-1",
        "tenant_id": "default",
        "user_id": "user-1",
        "user_role": "user",
    }

    async def run_tool():
        return await dispatcher.execute_tool("command", {"command": "ls -la"}, context=context)

    task = asyncio.create_task(run_tool())
    await asyncio.sleep(0.05)

    pending = db.list_pending_approval_requests(session_id="sess-1")
    assert len(pending) == 1
    assert pending[0].tool_name == "command"

    required_events = [e for _s, e in cm.personal if e.get("type") == "approval_required"]
    assert required_events
    assert required_events[0]["approval_id"] == pending[0].id

    await service.approve(pending[0].id, resolved_by="user-1")
    result = await task

    assert result.success is True
    assert "ran:ls -la" in result.output

    resolved_events = [e for _s, e in cm.personal if e.get("type") == "approval_resolved"]
    assert resolved_events
    assert resolved_events[-1]["status"] == "approved"


@pytest.mark.asyncio
async def test_command_tool_denied_returns_error(db, registry):
    cm = FakeConnectionManager()
    service = ApprovalService(db, cm, timeout_seconds=5)
    import tars.security.approval_service as approval_module

    approval_module.approval_service = service

    dispatcher = ToolDispatcher(registry)
    context = {
        "session_id": "sess-2",
        "tenant_id": "default",
        "user_id": "user-1",
        "user_role": "user",
    }

    task = asyncio.create_task(
        dispatcher.execute_tool("command", {"command": "rm -rf /"}, context=context)
    )
    await asyncio.sleep(0.05)
    pending = db.list_pending_approval_requests(session_id="sess-2")
    await service.deny(pending[0].id, resolved_by="user-1")
    result = await task

    assert result.success is False
    assert "拒绝" in (result.error or "")


@pytest.mark.asyncio
async def test_command_tool_timeout_when_not_approved(db, registry):
    cm = FakeConnectionManager()
    service = ApprovalService(db, cm, timeout_seconds=0.1)
    import tars.security.approval_service as approval_module

    approval_module.approval_service = service

    dispatcher = ToolDispatcher(registry)
    result = await dispatcher.execute_tool(
        "command",
        {"command": "sleep 1"},
        context={
            "session_id": "sess-3",
            "tenant_id": "default",
            "user_id": "user-1",
            "user_role": "user",
        },
    )

    assert result.success is False
    row = db._get_conn().execute(
        "SELECT status FROM approval_requests WHERE session_id = ?", ("sess-3",)
    ).fetchone()
    assert row[0] == "timeout"


@pytest.mark.asyncio
async def test_admin_role_skips_approval(db, registry):
    cm = FakeConnectionManager()
    service = ApprovalService(db, cm, timeout_seconds=5)
    import tars.security.approval_service as approval_module

    approval_module.approval_service = service

    dispatcher = ToolDispatcher(registry)
    result = await dispatcher.execute_tool(
        "command",
        {"command": "whoami"},
        context={
            "session_id": "sess-4",
            "tenant_id": "default",
            "user_id": "admin-1",
            "user_role": "admin",
        },
    )

    assert result.success is True
    assert db.list_pending_approval_requests(session_id="sess-4") == []


@pytest.mark.asyncio
async def test_dispatcher_denies_when_approval_service_missing(db, registry, monkeypatch):
    import tars.security.approval_service as approval_module
    import tars.security.execution_policy as policy_module
    from tars.security.execution_policy import ExecutionPolicy

    approval_module.approval_service = None
    policy_module.execution_policy = ExecutionPolicy()

    dispatcher = ToolDispatcher(registry)
    result = await dispatcher.execute_tool(
        "command",
        {"command": "ls"},
        context={
            "session_id": "sess-5",
            "tenant_id": "default",
            "user_id": "user-1",
            "user_role": "user",
        },
    )
    assert result.success is False
    assert "拒绝" in (result.error or "")


def test_authorize_request_rejects_other_user():
    from tars.api.approvals import _authorize_request
    from tars.api._auth import Principal
    from fastapi import HTTPException

    request = type("Req", (), {"user_id": "user-a", "tenant_id": "default"})()
    principal = Principal(
        user_id="user-b",
        role="user",
        role_template_id="default",
        tenant_id="default",
        is_admin=False,
        api_key="k",
    )
    with pytest.raises(HTTPException) as exc:
        _authorize_request(principal, request)
    assert exc.value.status_code == 403


def test_authorize_request_allows_admin():
    from tars.api.approvals import _authorize_request
    from tars.api._auth import Principal

    request = type("Req", (), {"user_id": "user-a", "tenant_id": "default"})()
    principal = Principal(
        user_id="admin-1",
        role="admin",
        role_template_id="admin",
        tenant_id="default",
        is_admin=True,
        api_key="k",
    )
    _authorize_request(principal, request)
