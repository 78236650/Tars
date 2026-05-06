"""TARS OS 工具 + 任务编排测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestWorkspaceSandbox:
    def test_resolve_within_workspace(self, tmp_path):
        from tars.tools.sandbox import WorkspaceSandbox
        sandbox = WorkspaceSandbox(str(tmp_path))
        resolved = sandbox.resolve("subdir/file.txt")
        assert str(resolved).startswith(str(tmp_path))

    def test_resolve_escape_blocked(self, tmp_path):
        from tars.tools.sandbox import WorkspaceSandbox
        sandbox = WorkspaceSandbox(str(tmp_path))
        with pytest.raises(PermissionError):
            sandbox.resolve("../../etc/passwd")

    def test_resolve_absolute_within(self, tmp_path):
        from tars.tools.sandbox import WorkspaceSandbox
        sandbox = WorkspaceSandbox(str(tmp_path))
        inner = tmp_path / "inner.txt"
        resolved = sandbox.resolve(str(inner))
        assert resolved == inner

    def test_resolve_absolute_outside(self, tmp_path):
        from tars.tools.sandbox import WorkspaceSandbox
        sandbox = WorkspaceSandbox(str(tmp_path))
        with pytest.raises(PermissionError):
            sandbox.resolve("/etc/passwd")

    def test_is_within(self, tmp_path):
        from tars.tools.sandbox import WorkspaceSandbox
        sandbox = WorkspaceSandbox(str(tmp_path))
        assert sandbox.is_within("file.txt") is True
        assert sandbox.is_within("../../etc") is False


class TestFileWriteTool:
    @pytest.mark.asyncio
    async def test_write_new_file(self, tmp_path):
        from tars.tools.sandbox import WorkspaceSandbox
        from tars.tools.builtin.file_write import FileWriteTool
        sandbox = WorkspaceSandbox(str(tmp_path))
        tool = FileWriteTool(sandbox)
        result = await tool.execute(path="hello.txt", content="Hello World")
        assert result.success is True
        assert (tmp_path / "hello.txt").read_text() == "Hello World"

    @pytest.mark.asyncio
    async def test_write_creates_dirs(self, tmp_path):
        from tars.tools.sandbox import WorkspaceSandbox
        from tars.tools.builtin.file_write import FileWriteTool
        sandbox = WorkspaceSandbox(str(tmp_path))
        tool = FileWriteTool(sandbox)
        result = await tool.execute(path="a/b/c/deep.txt", content="deep")
        assert result.success is True
        assert (tmp_path / "a/b/c/deep.txt").exists()

    @pytest.mark.asyncio
    async def test_append_mode(self, tmp_path):
        from tars.tools.sandbox import WorkspaceSandbox
        from tars.tools.builtin.file_write import FileWriteTool
        sandbox = WorkspaceSandbox(str(tmp_path))
        tool = FileWriteTool(sandbox)
        await tool.execute(path="log.txt", content="line1\n")
        await tool.execute(path="log.txt", content="line2\n", mode="append")
        assert (tmp_path / "log.txt").read_text() == "line1\nline2\n"

    @pytest.mark.asyncio
    async def test_insert_mode(self, tmp_path):
        from tars.tools.sandbox import WorkspaceSandbox
        from tars.tools.builtin.file_write import FileWriteTool
        sandbox = WorkspaceSandbox(str(tmp_path))
        tool = FileWriteTool(sandbox)
        (tmp_path / "code.py").write_text("line1\nline3\n")
        result = await tool.execute(path="code.py", content="line2", mode="insert", line=2)
        assert result.success is True
        assert "line2" in (tmp_path / "code.py").read_text()

    @pytest.mark.asyncio
    async def test_escape_blocked(self, tmp_path):
        from tars.tools.sandbox import WorkspaceSandbox
        from tars.tools.builtin.file_write import FileWriteTool
        sandbox = WorkspaceSandbox(str(tmp_path))
        tool = FileWriteTool(sandbox)
        result = await tool.execute(path="../../evil.txt", content="hack")
        assert result.success is False
        assert "超出" in result.error


class TestShellTool:
    @pytest.mark.asyncio
    async def test_basic_command(self, tmp_path):
        from tars.tools.sandbox import WorkspaceSandbox
        from tars.tools.builtin.shell import ShellTool
        sandbox = WorkspaceSandbox(str(tmp_path))
        tool = ShellTool(sandbox)
        result = await tool.execute(command="echo hello")
        assert result.success is True
        assert "hello" in result.output

    @pytest.mark.asyncio
    async def test_forbidden_command(self, tmp_path):
        from tars.tools.sandbox import WorkspaceSandbox
        from tars.tools.builtin.shell import ShellTool
        sandbox = WorkspaceSandbox(str(tmp_path))
        tool = ShellTool(sandbox)
        result = await tool.execute(command="rm -rf /")
        assert result.success is False
        assert "禁止" in result.error

    @pytest.mark.asyncio
    async def test_delete_needs_confirmation(self, tmp_path):
        from tars.tools.sandbox import WorkspaceSandbox
        from tars.tools.builtin.shell import ShellTool
        sandbox = WorkspaceSandbox(str(tmp_path))
        tool = ShellTool(sandbox)
        result = await tool.execute(command="rm temp.txt")
        assert result.success is False
        assert result.metadata.get("needs_confirmation") is True

    @pytest.mark.asyncio
    async def test_cwd_within_workspace(self, tmp_path):
        from tars.tools.sandbox import WorkspaceSandbox
        from tars.tools.builtin.shell import ShellTool
        sandbox = WorkspaceSandbox(str(tmp_path))
        tool = ShellTool(sandbox)
        (tmp_path / "subdir").mkdir()
        result = await tool.execute(command="pwd", cwd="subdir")
        assert result.success is True
        assert "subdir" in result.output


class TestProcessTool:
    @pytest.mark.asyncio
    async def test_list_processes(self):
        from tars.tools.builtin.process import ProcessTool
        tool = ProcessTool()
        result = await tool.execute(action="list")
        assert result.success is True
        assert "PID" in result.output or "pid" in result.output.lower()

    @pytest.mark.asyncio
    async def test_status_nonexistent(self):
        from tars.tools.builtin.process import ProcessTool
        tool = ProcessTool()
        result = await tool.execute(action="status", pid=99999)
        assert result.success is True
        assert "不存在" in result.output


class TestNetworkTool:
    @pytest.mark.asyncio
    async def test_port_check_open(self):
        from tars.tools.builtin.network import NetworkTool
        tool = NetworkTool()
        # 测试本地 8000 端口（后端正在运行）
        result = await tool.execute(action="port_check", host="localhost", port=8000)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_port_check_closed(self):
        from tars.tools.builtin.network import NetworkTool
        tool = NetworkTool()
        result = await tool.execute(action="port_check", host="localhost", port=19999)
        assert result.success is True
        assert "拒绝" in result.output or "超时" in result.output

    @pytest.mark.asyncio
    async def test_dns_lookup(self):
        from tars.tools.builtin.network import NetworkTool
        tool = NetworkTool()
        result = await tool.execute(action="dns_lookup", host="localhost")
        assert result.success is True
        assert "127.0.0.1" in result.output or "::1" in result.output


class TestOrchestration:
    def test_task_plan_from_dict(self):
        from tars.orchestration.models import TaskPlan
        plan = TaskPlan.from_dict({
            "goal": "创建项目",
            "steps": [
                {"id": 1, "description": "创建目录", "tool": "shell", "arguments": {"command": "mkdir app"}},
                {"id": 2, "description": "创建文件", "tool": "file_write", "arguments": {"path": "app/main.py", "content": "print('hi')"}},
            ]
        })
        assert plan.goal == "创建项目"
        assert len(plan.steps) == 2
        assert plan.steps[0].tool == "shell"

    @pytest.mark.asyncio
    async def test_task_planner_tool(self):
        from tars.orchestration.planner import TaskPlannerTool
        tool = TaskPlannerTool()
        result = await tool.execute(
            goal="测试计划",
            steps=[{"id": 1, "description": "echo", "tool": "shell", "arguments": {"command": "echo hi"}}]
        )
        assert result.success is True
        assert result.metadata.get("is_plan") is True
        plan = tool.pop_pending_plan()
        assert plan is not None
        assert plan.goal == "测试计划"

    def test_executor_resolve_placeholders(self):
        from tars.orchestration.executor import TaskExecutor
        from tars.tools.registry import ToolRegistry
        from tars.tools.base import ToolResult

        executor = TaskExecutor(ToolRegistry())
        results = {1: ToolResult(success=True, output="hello_world")}
        resolved = executor._resolve_placeholders({"cmd": "echo {{step_1.output}}"}, results)
        assert resolved["cmd"] == "echo hello_world"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
