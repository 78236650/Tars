"""
TARS Tools & Skills 系统全面功能测试
覆盖: BaseTool, ToolRegistry, ToolDispatcher, Skills, SkillHub
"""
import asyncio
import json
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

import pytest


# ============================================================
# 1. BaseTool & ToolResult 测试
# ============================================================

class TestBaseTool:
    def test_tool_result_success(self):
        from tars.tools.base import ToolResult
        r = ToolResult(success=True, output="hello")
        assert r.success is True
        assert r.output == "hello"
        assert r.error is None

    def test_tool_result_error(self):
        from tars.tools.base import ToolResult
        r = ToolResult(success=False, output="", error="something went wrong")
        assert r.success is False
        assert r.error == "something went wrong"

    def test_tool_function_schema(self):
        from tars.tools.base import BaseTool, ToolResult

        class DummyTool(BaseTool):
            name = "dummy"
            description = "A dummy tool"
            parameters_schema = {
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            }
            async def execute(self, **kwargs):
                return ToolResult(success=True, output=kwargs.get("x", ""))

        tool = DummyTool()
        schema = tool.to_function_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "dummy"
        assert schema["function"]["description"] == "A dummy tool"
        assert "x" in schema["function"]["parameters"]["properties"]


# ============================================================
# 2. ToolRegistry 测试
# ============================================================

class TestToolRegistry:
    def test_register_and_get(self):
        from tars.tools.registry import ToolRegistry
        from tars.tools.base import BaseTool, ToolResult

        class FakeTool(BaseTool):
            name = "fake"
            description = "fake tool"
            parameters_schema = {}
            async def execute(self, **kwargs):
                return ToolResult(success=True, output="ok")

        reg = ToolRegistry()
        tool = FakeTool()
        reg.register(tool)

        assert reg.get("fake") is tool
        assert "fake" in reg.list_names()
        assert len(reg.list_all()) == 1

    def test_unregister(self):
        from tars.tools.registry import ToolRegistry
        from tars.tools.base import BaseTool, ToolResult

        class FakeTool(BaseTool):
            name = "temp"
            description = ""
            parameters_schema = {}
            async def execute(self, **kwargs):
                return ToolResult(success=True, output="")

        reg = ToolRegistry()
        reg.register(FakeTool())
        reg.unregister("temp")
        assert reg.get("temp") is None

    def test_get_function_schemas(self):
        from tars.tools.registry import ToolRegistry
        from tars.tools.base import BaseTool, ToolResult

        class T1(BaseTool):
            name = "t1"
            description = "tool 1"
            parameters_schema = {"type": "object", "properties": {}}
            async def execute(self, **kwargs):
                return ToolResult(success=True, output="")

        class T2(BaseTool):
            name = "t2"
            description = "tool 2"
            parameters_schema = {"type": "object", "properties": {}}
            async def execute(self, **kwargs):
                return ToolResult(success=True, output="")

        reg = ToolRegistry()
        reg.register(T1())
        reg.register(T2())
        schemas = reg.get_function_schemas()
        assert len(schemas) == 2
        names = [s["function"]["name"] for s in schemas]
        assert "t1" in names
        assert "t2" in names


# ============================================================
# 3. ToolDispatcher 测试
# ============================================================

class TestToolDispatcher:
    def test_supports_native_tools(self):
        from tars.tools.dispatcher import ToolDispatcher
        from tars.tools.registry import ToolRegistry

        reg = ToolRegistry()
        d = ToolDispatcher(reg)
        assert d.supports_native_tools("qwen3:4b") is True
        assert d.supports_native_tools("llama3.2:latest") is True
        assert d.supports_native_tools("phi3") is False

    def test_parse_tool_call_from_text_json_block(self):
        from tars.tools.dispatcher import ToolDispatcher
        from tars.tools.registry import ToolRegistry

        reg = ToolRegistry()
        d = ToolDispatcher(reg)

        text = '好的，让我查询天气。\n```json\n{"tool_call": {"name": "weather", "arguments": {"city": "上海"}}}\n```'
        result = d._parse_tool_call_from_text(text)
        assert result is not None
        assert result[0] == "weather"
        assert result[1] == {"city": "上海"}

    def test_parse_tool_call_from_text_no_match(self):
        from tars.tools.dispatcher import ToolDispatcher
        from tars.tools.registry import ToolRegistry

        reg = ToolRegistry()
        d = ToolDispatcher(reg)

        text = "今天天气不错，适合出门散步。"
        result = d._parse_tool_call_from_text(text)
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        from tars.tools.dispatcher import ToolDispatcher
        from tars.tools.registry import ToolRegistry
        from tars.tools.base import BaseTool, ToolResult

        class EchoTool(BaseTool):
            name = "echo"
            description = "echo"
            parameters_schema = {}
            async def execute(self, **kwargs):
                return ToolResult(success=True, output=kwargs.get("msg", ""))

        reg = ToolRegistry()
        reg.register(EchoTool())
        d = ToolDispatcher(reg)

        result = await d.execute_tool("echo", {"msg": "hello"})
        assert result.success is True
        assert result.output == "hello"

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        from tars.tools.dispatcher import ToolDispatcher
        from tars.tools.registry import ToolRegistry

        reg = ToolRegistry()
        d = ToolDispatcher(reg)

        result = await d.execute_tool("nonexistent", {})
        assert result.success is False
        assert "不存在" in result.error


# ============================================================
# 4. 内置工具测试
# ============================================================

class TestBuiltinWeather:
    @pytest.mark.asyncio
    async def test_weather_mock(self):
        from tars.tools.builtin.weather import WeatherTool
        tool = WeatherTool()  # 无 API key，使用 mock
        result = await tool.execute(city="北京")
        assert result.success is True
        assert "北京" in result.output

    @pytest.mark.asyncio
    async def test_weather_no_city(self):
        from tars.tools.builtin.weather import WeatherTool
        tool = WeatherTool()
        result = await tool.execute()
        assert result.success is False
        assert "城市" in result.error


class TestBuiltinFile:
    @pytest.mark.asyncio
    async def test_file_read(self, tmp_path):
        from tars.tools.builtin.file import FileTool
        test_file = tmp_path / "test.txt"
        test_file.write_text("line1\nline2\nline3\n")

        tool = FileTool()
        result = await tool.execute(path=str(test_file))
        assert result.success is True
        assert "line1" in result.output

    @pytest.mark.asyncio
    async def test_file_read_not_found(self):
        from tars.tools.builtin.file import FileTool
        tool = FileTool()
        result = await tool.execute(path="/nonexistent/file.txt")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_file_list(self, tmp_path):
        from tars.tools.builtin.file import FileListTool
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.txt").write_text("y")
        (tmp_path / "subdir").mkdir()

        tool = FileListTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is True
        assert "a.py" in result.output
        assert "subdir" in result.output


class TestBuiltinCommand:
    @pytest.mark.asyncio
    async def test_command_allowed(self):
        from tars.tools.builtin.command import CommandTool
        tool = CommandTool()
        result = await tool.execute(command="echo hello")
        assert result.success is True
        assert "hello" in result.output

    @pytest.mark.asyncio
    async def test_command_forbidden(self):
        from tars.tools.builtin.command import CommandTool
        tool = CommandTool()
        result = await tool.execute(command="rm -rf /")
        assert result.success is False
        assert "白名单" in result.error or "危险" in result.error

    @pytest.mark.asyncio
    async def test_command_not_in_whitelist(self):
        from tars.tools.builtin.command import CommandTool
        tool = CommandTool()
        result = await tool.execute(command="some_random_binary --flag")
        assert result.success is False


class TestBuiltinWeb:
    @pytest.mark.asyncio
    async def test_web_no_url(self):
        from tars.tools.builtin.web import WebTool
        tool = WebTool()
        result = await tool.execute()
        assert result.success is False
        assert "URL" in result.error


# ============================================================
# 5. Skills v2 测试
# ============================================================

class TestSkillBase:
    def test_skill_to_dict(self):
        from tars.skills.base import Skill, SkillType, SkillParameter
        skill = Skill(
            id="test",
            name="Test Skill",
            description="A test",
            type=SkillType.PROMPT,
            prompt_template="Hello {name}",
            parameters=[SkillParameter(name="name", type="string", required=True)],
        )
        d = skill.to_dict()
        assert d["id"] == "test"
        assert d["type"] == "prompt"
        assert d["prompt_template"] == "Hello {name}"
        assert len(d["parameters"]) == 1


class TestSkillRegistry:
    def test_register_and_list(self):
        from tars.skills.registry import SkillRegistry
        from tars.skills.base import Skill, SkillType

        reg = SkillRegistry()
        s = Skill(id="s1", name="S1", description="", type=SkillType.PROMPT, prompt_template="hi")
        reg.register(s)
        assert reg.get("s1") is s
        assert len(reg.list_all()) == 1

    def test_enable_disable(self):
        from tars.skills.registry import SkillRegistry
        from tars.skills.base import Skill, SkillType

        reg = SkillRegistry()
        s = Skill(id="s2", name="S2", description="", type=SkillType.PLUGIN, enabled=True)
        reg.register(s)

        reg.disable("s2")
        assert s.enabled is False

        reg.enable("s2")
        assert s.enabled is True

    def test_list_prompt_skills(self):
        from tars.skills.registry import SkillRegistry
        from tars.skills.base import Skill, SkillType

        reg = SkillRegistry()
        reg.register(Skill(id="p1", name="P1", description="", type=SkillType.PROMPT, prompt_template="x", enabled=True))
        reg.register(Skill(id="p2", name="P2", description="", type=SkillType.PLUGIN, enabled=True))
        reg.register(Skill(id="p3", name="P3", description="", type=SkillType.PROMPT, prompt_template="y", enabled=False))

        prompts = reg.list_prompt_skills()
        assert len(prompts) == 1
        assert prompts[0].id == "p1"


class TestSkillLoader:
    def test_load_prompt_skill(self, tmp_path):
        import yaml
        from tars.skills.loader import SkillLoader
        from tars.skills.registry import SkillRegistry
        from tars.tools.registry import ToolRegistry

        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "skill.yaml").write_text(yaml.dump({
            "id": "my-skill",
            "name": "My Skill",
            "description": "test prompt skill",
            "type": "prompt",
            "prompt_template": "You are a helpful assistant.",
        }))

        sr = SkillRegistry()
        tr = ToolRegistry()
        loader = SkillLoader(str(tmp_path), tool_registry=tr, skill_registry=sr)
        skills = loader.load_all()

        assert len(skills) == 1
        assert skills[0].id == "my-skill"
        assert skills[0].prompt_template == "You are a helpful assistant."
        assert sr.get("my-skill") is not None

    def test_load_plugin_skill(self, tmp_path):
        import yaml
        from tars.skills.loader import SkillLoader
        from tars.skills.registry import SkillRegistry
        from tars.tools.registry import ToolRegistry

        skill_dir = tmp_path / "calc"
        skill_dir.mkdir()
        (skill_dir / "skill.yaml").write_text(yaml.dump({
            "id": "calc",
            "name": "Calculator",
            "description": "math",
            "type": "plugin",
            "entry_point": "main.py",
        }))
        (skill_dir / "main.py").write_text("""
from tars.tools.base import BaseTool, ToolResult

class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Calculate math expressions"
    parameters_schema = {"type": "object", "properties": {"expr": {"type": "string"}}, "required": ["expr"]}

    async def execute(self, **kwargs):
        expr = kwargs.get("expr", "0")
        try:
            result = eval(expr)
            return ToolResult(success=True, output=str(result))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
""")

        sr = SkillRegistry()
        tr = ToolRegistry()
        loader = SkillLoader(str(tmp_path), tool_registry=tr, skill_registry=sr)
        skills = loader.load_all()

        assert len(skills) == 1
        assert skills[0].type.value == "plugin"
        # 插件应该被注册为 Tool
        assert tr.get("calculator") is not None


class TestSkillExecutor:
    def test_build_prompt_injection(self):
        from tars.skills.executor import SkillExecutor
        from tars.skills.registry import SkillRegistry
        from tars.skills.base import Skill, SkillType

        reg = SkillRegistry()
        reg.register(Skill(id="w", name="Writer", description="", type=SkillType.PROMPT, prompt_template="Write well.", enabled=True))
        reg.register(Skill(id="c", name="Coder", description="", type=SkillType.PROMPT, prompt_template="Code well.", enabled=True))

        executor = SkillExecutor(reg)
        injection = executor.build_prompt_injection()
        assert "Write well." in injection
        assert "Code well." in injection


# ============================================================
# 6. SkillHub 测试
# ============================================================

class TestSkillHubModels:
    def test_package_to_dict(self):
        from tars.skillhub.models import SkillHubPackage
        pkg = SkillHubPackage(
            id="user/repo",
            name="repo",
            description="A skill",
            author="user",
            version="1.0.0",
            stars=42,
        )
        d = pkg.to_dict()
        assert d["id"] == "user/repo"
        assert d["stars"] == 42


class TestSkillHubInstaller:
    def test_list_installed_empty(self, tmp_path):
        from tars.skillhub.installer import SkillInstaller
        installer = SkillInstaller(str(tmp_path / "skills"), client=None)
        assert installer.list_installed() == []

    def test_uninstall_not_found(self, tmp_path):
        from tars.skillhub.installer import SkillInstaller
        installer = SkillInstaller(str(tmp_path / "skills"), client=None)
        result = installer.uninstall("nonexistent")
        assert result["success"] is False


# ============================================================
# 7. Plugin Loader 测试
# ============================================================

class TestPluginLoader:
    def test_load_valid_plugin(self, tmp_path):
        from tars.tools.plugin_loader import load_plugin_tool

        plugin_file = tmp_path / "my_tool.py"
        plugin_file.write_text("""
from tars.tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "test"
    parameters_schema = {}
    async def execute(self, **kwargs):
        return ToolResult(success=True, output="loaded!")
""")

        tool = load_plugin_tool(plugin_file)
        assert tool is not None
        assert tool.name == "my_tool"

    def test_load_nonexistent(self, tmp_path):
        from tars.tools.plugin_loader import load_plugin_tool
        result = load_plugin_tool(tmp_path / "nope.py")
        assert result is None


# ============================================================
# 8. API 路由测试
# ============================================================

class TestToolsAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from tars.api.tools import router
        from tars.tools.registry import ToolRegistry
        from tars.tools.base import BaseTool, ToolResult

        # 创建测试 app
        app = FastAPI()
        app.include_router(router)

        # 注册一个测试工具
        class TestTool(BaseTool):
            name = "test_tool"
            description = "A test tool"
            parameters_schema = {"type": "object", "properties": {"msg": {"type": "string"}}, "required": ["msg"]}
            async def execute(self, **kwargs):
                return ToolResult(success=True, output=f"echo: {kwargs.get('msg', '')}")

        from tars.tools import registry
        registry.clear()
        registry.register(TestTool())

        return TestClient(app)

    def test_list_tools(self, client):
        resp = client.get("/api/tools/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tools"]) == 1
        assert data["tools"][0]["id"] == "test_tool"

    def test_get_tool_detail(self, client):
        resp = client.get("/api/tools/test_tool")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test_tool"

    def test_get_tool_not_found(self, client):
        resp = client.get("/api/tools/nonexistent")
        assert resp.status_code == 404

    def test_execute_tool(self, client):
        resp = client.post("/api/tools/execute", json={"tool_name": "test_tool", "parameters": {"msg": "hi"}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "echo: hi" in data["output"]


class TestSkillsAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from tars.api.skills import router
        from tars.skills import skill_registry

        app = FastAPI()
        app.include_router(router)

        skill_registry.clear()
        return TestClient(app)

    def test_list_skills_empty(self, client):
        resp = client.get("/api/skills/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_create_prompt_skill(self, client):
        resp = client.post("/api/skills/create-prompt", json={
            "id": "writer",
            "name": "Writer",
            "description": "Writing assistant",
            "prompt_template": "You are a writer.",
            "tags": ["writing"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["skill"]["type"] == "prompt"

        # 验证已注册
        resp2 = client.get("/api/skills/")
        assert resp2.json()["total"] == 1

    def test_delete_skill(self, client):
        # 先创建
        client.post("/api/skills/create-prompt", json={
            "id": "temp",
            "name": "Temp",
            "description": "temp",
            "prompt_template": "x",
        })
        # 再删除
        resp = client.delete("/api/skills/temp")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # 验证已删除
        resp2 = client.get("/api/skills/")
        assert resp2.json()["total"] == 0


# ============================================================
# 运行入口
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
