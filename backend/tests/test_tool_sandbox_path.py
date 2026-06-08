"""S3: 工具沙箱绝对路径拦截测试"""
import pytest

from tars.tools.builtin.shell import ShellTool
from tars.tools.builtin.python_exec import PythonExecTool
from tars.tools.sandbox import WorkspaceSandbox
from tars.tools.base import ToolResult
from tars.tools.dispatcher import ToolDispatcher
from tars.tools.registry import ToolRegistry


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


# ---- shell 绝对路径拦截 ----

@pytest.mark.asyncio
async def test_shell_blocks_cat_etc_passwd(workspace):
    tool = ShellTool(WorkspaceSandbox(str(workspace)))
    result = await tool.execute(
        command="cat /etc/passwd",
        _workspace_dir=str(workspace),
        _allowed_dirs=[str(workspace)],
    )
    assert result.success is False
    assert "受保护路径" in (result.error or "")


@pytest.mark.asyncio
async def test_shell_blocks_redirect_to_etc(workspace):
    tool = ShellTool(WorkspaceSandbox(str(workspace)))
    result = await tool.execute(
        command="echo hi > /etc/evil.conf",
        _workspace_dir=str(workspace),
        _allowed_dirs=[str(workspace)],
    )
    assert result.success is False


@pytest.mark.asyncio
async def test_shell_allows_workspace_relative(workspace):
    (workspace / "a.txt").write_text("hello")
    tool = ShellTool(WorkspaceSandbox(str(workspace)))
    result = await tool.execute(
        command="cat a.txt",
        _workspace_dir=str(workspace),
        _allowed_dirs=[str(workspace)],
    )
    assert result.success is True
    assert "hello" in result.output


@pytest.mark.asyncio
async def test_shell_allows_absolute_path_inside_workspace(workspace):
    (workspace / "b.txt").write_text("world")
    tool = ShellTool(WorkspaceSandbox(str(workspace)))
    result = await tool.execute(
        command=f"cat {workspace}/b.txt",
        _workspace_dir=str(workspace),
        _allowed_dirs=[str(workspace)],
    )
    assert result.success is True
    assert "world" in result.output


@pytest.mark.asyncio
async def test_shell_allows_dev_null_redirect(workspace):
    tool = ShellTool(WorkspaceSandbox(str(workspace)))
    result = await tool.execute(
        command="echo hi 2>/dev/null",
        _workspace_dir=str(workspace),
        _allowed_dirs=[str(workspace)],
    )
    assert result.success is True


# ---- python_exec open 拦截 ----

@pytest.mark.asyncio
async def test_python_blocks_open_etc_passwd(workspace):
    tool = PythonExecTool(workspace_dir=str(workspace))
    result = await tool.execute(
        code="open('/etc/passwd').read()",
        _workspace_dir=str(workspace),
        _tmp_dir=str(workspace),
        _allowed_dirs=[str(workspace)],
    )
    assert result.success is False
    assert "PermissionError" in (result.error or "") or "禁止" in (result.error or "")


@pytest.mark.asyncio
async def test_python_allows_open_inside_workspace(workspace):
    tool = PythonExecTool(workspace_dir=str(workspace))
    result = await tool.execute(
        code=(
            "open('out.txt','w').write('ok')\n"
            "print(open('out.txt').read())"
        ),
        _workspace_dir=str(workspace),
        _tmp_dir=str(workspace),
        _allowed_dirs=[str(workspace)],
    )
    assert result.success is True
    assert "ok" in result.output


@pytest.mark.asyncio
async def test_python_blocks_os_system(workspace):
    tool = PythonExecTool(workspace_dir=str(workspace))
    result = await tool.execute(
        code="import os; os.system('echo pwned')",
        _workspace_dir=str(workspace),
        _tmp_dir=str(workspace),
        _allowed_dirs=[str(workspace)],
    )
    assert result.success is False


# ---- dispatcher fail-closed ----

class _ShellStub(ShellTool):
    pass


@pytest.mark.asyncio
async def test_dispatcher_fail_closed_when_workspace_manager_missing(monkeypatch):
    import tars.tools.tenant_workspace as tw
    monkeypatch.setattr(tw, "tenant_workspace_manager", None)

    import tars.security.execution_policy as policy_module
    from tars.security.execution_policy import ExecutionPolicy
    policy_module.execution_policy = ExecutionPolicy()
    import tars.security.approval_service as approval_module
    approval_module.approval_service = None

    reg = ToolRegistry()
    reg.register(ShellTool(WorkspaceSandbox("/tmp")))
    dispatcher = ToolDispatcher(reg)
    result = await dispatcher.execute_tool(
        "shell",
        {"command": "echo hi"},
        context={"tenant_id": "default", "user_id": "u", "user_role": "admin"},
    )
    assert result.success is False
    assert "高危工具" in (result.error or "") or "拒绝" in (result.error or "")
