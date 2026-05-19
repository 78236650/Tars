"""v4.1 SkillHub skills.sh + router tests"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


class TestSkillsConfig:
    def test_load_defaults(self):
        import tars.config.skills as mod
        mod._CONFIG = None
        from tars.config.skills import SkillsConfig
        cfg = SkillsConfig()
        assert cfg.skill_top_k == 3
        assert cfg.router_enabled is True


class TestSkillsShClient:
    @pytest.mark.asyncio
    async def test_search_from_seed(self, tmp_path):
        from tars.skillhub.skills_sh_client import SkillsShClient

        seed = tmp_path / "skills_sh_seed.json"
        seed.write_text(json.dumps([{
            "id": "skills_sh/demo/repo",
            "name": "demo",
            "description": "demo skill",
            "author": "demo",
            "version": "1.0.0",
            "type": "prompt",
            "tags": ["demo"],
            "source": "skills_sh",
            "github_repo": "demo/repo",
        }]), encoding="utf-8")

        cache = tmp_path / "skills_sh_index.json"
        client = SkillsShClient(str(cache), enabled=True)

        async def fake_refresh():
            return json.loads(seed.read_text())

        with patch.object(client, "_refresh_index", side_effect=fake_refresh):
            results = await client.search("demo")
        assert len(results) == 1
        assert results[0].name == "demo"


class TestDependencyChecker:
    def test_missing_bin(self):
        from tars.skillhub.dependency_checker import DependencyChecker

        report = DependencyChecker().check({"requires": {"bins": ["definitely-not-a-real-bin-xyz"]}})
        assert report.ok is False
        assert "definitely-not-a-real-bin-xyz" in report.missing_bins


class TestSkillRouterIntegration:
    def test_route_from_content_pdf(self):
        from tars.skills.router import SkillRouter
        from tars.skills.registry import SkillRegistry
        from tars.skills.base import Skill, SkillType
        from tars.config.skills import SkillsConfig

        reg = SkillRegistry()
        reg.register(Skill(
            id="pdf",
            name="pdf",
            description="PDF manipulation toolkit",
            type=SkillType.PROMPT,
            prompt_template="Use pypdf.",
            enabled=True,
            tags=["pdf"],
        ))
        router = SkillRouter(reg, SkillsConfig())
        matched = router.route_from_content("帮我处理这个 PDF 文件")
        assert len(matched) >= 1
        assert matched[0][0].id == "pdf"

    def test_route_from_content_uses_scene_intent(self):
        from tars.skills.router import SkillRouter
        from tars.skills.registry import SkillRegistry
        from tars.skills.base import Skill, SkillType
        from tars.config.skills import SkillsConfig

        reg = SkillRegistry()
        reg.register(Skill(
            id="sql_helper",
            name="SQL 助手",
            description="SQL queries",
            type=SkillType.PROMPT,
            prompt_template="Write SQL.",
            enabled=True,
            trigger_intents=["data.analyze"],
            trigger_keywords=["sql"],
        ))
        router = SkillRouter(reg, SkillsConfig())
        matched = router.route_from_content(
            "看一下",
            scene_intent="data.analyze",
            scene_keywords=["sales"],
        )
        assert any(s.id == "sql_helper" for s, _ in matched)


class TestSkillReload:
    def test_reload_all(self, tmp_path):
        import yaml
        from tars.skills.loader import SkillLoader
        from tars.skills.registry import SkillRegistry
        from tars.tools.registry import ToolRegistry

        skill_dir = tmp_path / "note"
        skill_dir.mkdir()
        (skill_dir / "skill.yaml").write_text(yaml.dump({
            "id": "note",
            "name": "Note",
            "description": "notes",
            "type": "prompt",
            "prompt_template": "Take notes.",
        }), encoding="utf-8")

        sr = SkillRegistry()
        tr = ToolRegistry()
        loader = SkillLoader(str(tmp_path), tool_registry=tr, skill_registry=sr)
        first = loader.load_all()
        assert len(first) == 1

        sr.unregister("note")
        second = loader.reload_all()
        assert len(second) == 1
        assert sr.get("note") is not None
