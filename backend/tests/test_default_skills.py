"""TARS 默认技能功能测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


class TestDefaultSkillsLoading:
    def test_load_all_default_skills(self):
        """验证所有 5 个默认技能能被加载"""
        from tars.tools.registry import ToolRegistry
        from tars.skills import SkillRegistry, SkillLoader

        tr = ToolRegistry()
        sr = SkillRegistry()
        loader = SkillLoader(skills_dir=str(SKILLS_DIR), tool_registry=tr, skill_registry=sr)
        skills = loader.load_all()

        skill_ids = {s.id for s in skills}
        expected = {"calculator", "code_assistant", "summarizer", "translator", "planner"}
        assert expected.issubset(skill_ids), f"缺失技能: {expected - skill_ids}"

    def test_calculator_is_plugin(self):
        """Calculator 应该是 plugin 类型，并注册为 tool"""
        from tars.tools.registry import ToolRegistry
        from tars.skills import SkillRegistry, SkillLoader, SkillType

        tr = ToolRegistry()
        sr = SkillRegistry()
        SkillLoader(skills_dir=str(SKILLS_DIR), tool_registry=tr, skill_registry=sr).load_all()

        calc = sr.get("calculator")
        assert calc is not None
        assert calc.type == SkillType.PLUGIN
        assert tr.get("calculator") is not None

    def test_prompt_skills_are_prompt_type(self):
        """code_assistant/summarizer/translator/planner 应该是 prompt 类型"""
        from tars.tools.registry import ToolRegistry
        from tars.skills import SkillRegistry, SkillLoader, SkillType

        tr = ToolRegistry()
        sr = SkillRegistry()
        SkillLoader(skills_dir=str(SKILLS_DIR), tool_registry=tr, skill_registry=sr).load_all()

        for skill_id in ["code_assistant", "summarizer", "translator", "planner"]:
            s = sr.get(skill_id)
            assert s is not None, f"{skill_id} 未加载"
            assert s.type == SkillType.PROMPT
            assert s.prompt_template, f"{skill_id} 缺少 prompt_template"


class TestCalculatorSkill:
    @pytest.fixture
    def calculator(self):
        from tars.tools.registry import ToolRegistry
        from tars.skills import SkillRegistry, SkillLoader

        tr = ToolRegistry()
        SkillLoader(skills_dir=str(SKILLS_DIR), tool_registry=tr, skill_registry=SkillRegistry()).load_all()
        return tr.get("calculator")

    @pytest.mark.asyncio
    async def test_basic_arithmetic(self, calculator):
        result = await calculator.execute(expression="2 + 3 * 4")
        assert result.success is True
        assert "14" in result.output

    @pytest.mark.asyncio
    async def test_division(self, calculator):
        result = await calculator.execute(expression="10 / 4")
        assert result.success is True
        assert "2.5" in result.output

    @pytest.mark.asyncio
    async def test_power(self, calculator):
        result = await calculator.execute(expression="2 ** 10")
        assert result.success is True
        assert "1024" in result.output

    @pytest.mark.asyncio
    async def test_math_functions(self, calculator):
        result = await calculator.execute(expression="sqrt(16) + log(e)")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_trig(self, calculator):
        result = await calculator.execute(expression="sin(0) + cos(0)")
        assert result.success is True
        assert "1" in result.output

    @pytest.mark.asyncio
    async def test_constants(self, calculator):
        result = await calculator.execute(expression="pi")
        assert result.success is True
        assert "3.14" in result.output

    @pytest.mark.asyncio
    async def test_division_by_zero(self, calculator):
        result = await calculator.execute(expression="1 / 0")
        assert result.success is False
        assert "除零" in result.error

    @pytest.mark.asyncio
    async def test_invalid_expression(self, calculator):
        result = await calculator.execute(expression="import os")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_empty_expression(self, calculator):
        result = await calculator.execute(expression="")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_forbidden_function(self, calculator):
        """危险函数应被拒绝"""
        result = await calculator.execute(expression="__import__('os').system('ls')")
        assert result.success is False


class TestPromptSkillsInjection:
    def test_prompt_injection_contains_skills(self):
        """验证激活的 PromptSkill 会注入到 prompt"""
        from tars.tools.registry import ToolRegistry
        from tars.skills import SkillRegistry, SkillLoader, SkillExecutor

        tr = ToolRegistry()
        sr = SkillRegistry()
        SkillLoader(skills_dir=str(SKILLS_DIR), tool_registry=tr, skill_registry=sr).load_all()

        executor = SkillExecutor(sr)
        injection = executor.build_prompt_injection()

        # 所有激活的 PromptSkill 内容应出现
        assert "代码助手" in injection
        assert "摘要" in injection
        assert "翻译" in injection
        assert "任务规划" in injection

    def test_disabled_skill_not_injected(self):
        """禁用的 PromptSkill 不应被注入"""
        from tars.tools.registry import ToolRegistry
        from tars.skills import SkillRegistry, SkillLoader, SkillExecutor

        tr = ToolRegistry()
        sr = SkillRegistry()
        SkillLoader(skills_dir=str(SKILLS_DIR), tool_registry=tr, skill_registry=sr).load_all()

        sr.disable("translator")

        executor = SkillExecutor(sr)
        injection = executor.build_prompt_injection()

        assert "翻译助手" not in injection
        # 其他仍在
        assert "代码助手" in injection


class TestSkillAPIIntegration:
    @pytest.fixture
    def client(self, tmp_path):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from tars.api.skills import router
        from tars.database import Database
        from tars.skills import skill_registry
        from tars.tools.registry import ToolRegistry
        from tars.skills.loader import SkillLoader

        from tests.conftest import setup_main_api_auth

        # 加载默认技能
        skill_registry.clear()
        loader = SkillLoader(skills_dir=str(SKILLS_DIR), tool_registry=ToolRegistry(), skill_registry=skill_registry)
        loader.load_all()

        db = Database(str(tmp_path / "skills.db"))
        auth_headers, _user = setup_main_api_auth(db)
        app = FastAPI()
        app.include_router(router)
        return TestClient(app), auth_headers

    def test_list_default_skills(self, client):
        test_client, headers = client
        resp = test_client.get("/api/skills/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        skill_ids = [s["id"] for s in data["skills"]]
        for expected_id in ["calculator", "code_assistant", "summarizer", "translator", "planner"]:
            assert expected_id in skill_ids, f"技能 {expected_id} 未返回"

    def test_get_skill_detail_includes_prompt(self, client):
        test_client, headers = client
        resp = test_client.get("/api/skills/code_assistant", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        skill = data["skill"]
        assert skill["type"] == "prompt"
        assert "prompt_template" in skill
        assert skill["prompt_template"]
        assert "代码质量" in skill["prompt_template"]

    def test_disable_then_enable(self, client):
        test_client, headers = client
        resp1 = test_client.put("/api/skills/translator/disable", headers=headers)
        assert resp1.status_code == 200

        resp2 = test_client.get("/api/skills/translator", headers=headers)
        assert resp2.json()["skill"]["enabled"] is False

        resp3 = test_client.put("/api/skills/translator/enable", headers=headers)
        assert resp3.status_code == 200

        resp4 = test_client.get("/api/skills/translator", headers=headers)
        assert resp4.json()["skill"]["enabled"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
