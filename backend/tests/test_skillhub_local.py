"""SkillHub 本地目录与安装测试"""
import json
from pathlib import Path

import pytest


@pytest.fixture
def skillhub_bundle(tmp_path):
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "demo-skill.md").write_text(
        "---\nname: demo-skill\ndescription: Demo skill for tests\n---\n\n# Demo\nDo demo things.\n",
        encoding="utf-8",
    )
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(
        json.dumps([{
            "id": "bundled/demo-skill",
            "name": "Demo Skill",
            "description": "Demo skill for tests",
            "author": "Test",
            "version": "1.0.0",
            "type": "prompt",
            "tags": ["demo"],
            "source": "bundled",
            "bundle_file": "demo-skill.md",
            "usage": "Say demo",
            "example_prompt": "Run a demo",
            "featured": True,
        }]),
        encoding="utf-8",
    )
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    return {
        "bundle_dir": bundle_dir,
        "catalog_path": catalog_path,
        "skills_dir": skills_dir,
    }


class TestLocalSkillCatalog:
    def test_load_entries_from_catalog_and_bundle(self, skillhub_bundle):
        from tars.skillhub.local_catalog import LocalSkillCatalog

        catalog = LocalSkillCatalog(
            catalog_path=str(skillhub_bundle["catalog_path"]),
            bundle_dir=str(skillhub_bundle["bundle_dir"]),
        )
        entries = catalog.load_entries()
        assert len(entries) >= 1
        assert any(e["id"] == "bundled/demo-skill" for e in entries)

    def test_search_by_keyword(self, skillhub_bundle):
        from tars.skillhub.local_catalog import LocalSkillCatalog

        catalog = LocalSkillCatalog(
            catalog_path=str(skillhub_bundle["catalog_path"]),
            bundle_dir=str(skillhub_bundle["bundle_dir"]),
        )
        results = catalog.search("demo")
        assert len(results) == 1
        assert results[0].name == "Demo Skill"

    def test_resolve_bundled_source(self, skillhub_bundle):
        from tars.skillhub.local_catalog import LocalSkillCatalog

        catalog = LocalSkillCatalog(
            catalog_path=str(skillhub_bundle["catalog_path"]),
            bundle_dir=str(skillhub_bundle["bundle_dir"]),
        )
        source = catalog.resolve_install_source("bundled/demo-skill")
        assert source is not None
        assert source["type"] == "bundled"
        assert source["path"].exists()


class TestSkillHubLocalInstall:
    @pytest.mark.asyncio
    async def test_install_bundled_skill(self, skillhub_bundle):
        from tars.skillhub.local_catalog import LocalSkillCatalog
        from tars.skillhub.installer import SkillInstaller
        from tars.skills.loader import SkillLoader
        from tars.skills.registry import SkillRegistry
        from tars.tools.registry import ToolRegistry

        sr = SkillRegistry()
        tr = ToolRegistry()
        loader = SkillLoader(
            str(skillhub_bundle["skills_dir"]),
            tool_registry=tr,
            skill_registry=sr,
        )
        catalog = LocalSkillCatalog(
            catalog_path=str(skillhub_bundle["catalog_path"]),
            bundle_dir=str(skillhub_bundle["bundle_dir"]),
        )
        installer = SkillInstaller(
            skills_dir=str(skillhub_bundle["skills_dir"]),
            client=None,
            skill_loader=loader,
            skill_registry=sr,
            local_catalog=catalog,
        )

        result = await installer.install("bundled/demo-skill")
        assert result["success"] is True
        assert result["skill_id"] == "demo-skill"
        assert result.get("ready") is True
        assert (skillhub_bundle["skills_dir"] / "tenants" / "default" / "demo-skill" / "SKILL.md").exists()
        assert sr.get("demo-skill", "default") is not None

    def test_contextual_skill_injection(self, skillhub_bundle):
        from tars.skills.loader import SkillLoader
        from tars.skills.registry import SkillRegistry
        from tars.skills.base import Skill, SkillType
        from tars.tools.registry import ToolRegistry

        sr = SkillRegistry()
        sr.register(Skill(
            id="pdf",
            name="pdf",
            description="PDF manipulation toolkit",
            type=SkillType.PROMPT,
            prompt_template="Use pypdf for PDF tasks.",
            enabled=True,
            tags=["pdf"],
        ))
        loader = SkillLoader(str(skillhub_bundle["skills_dir"]), skill_registry=sr, tool_registry=ToolRegistry())
        injection = loader.get_contextual_skill_injection("帮我处理这个 PDF 文件")
        assert "pypdf" in injection
