"""v4.1 Phase 3 — tenant-scoped skill isolation tests"""
import json
from pathlib import Path

import pytest


class TestTenantSkillPaths:
    def test_install_target_global_and_tenant(self, tmp_path):
        from tars.skills.tenant_paths import TenantSkillPaths

        paths = TenantSkillPaths(str(tmp_path))
        global_target = paths.install_target("pdf-tool", "global")
        tenant_target = paths.install_target("pdf-tool", "tenant", "user-a")

        assert global_target == tmp_path / "_global" / "pdf-tool"
        assert tenant_target == tmp_path / "tenants" / "user-a" / "pdf-tool"

    def test_migrate_flat_to_global(self, tmp_path):
        from tars.skills.tenant_paths import TenantSkillPaths

        legacy = tmp_path / "calculator"
        legacy.mkdir()
        (legacy / "SKILL.md").write_text("---\nname: calculator\n---\nbody", encoding="utf-8")

        paths = TenantSkillPaths(str(tmp_path))
        moved = paths.migrate_flat_to_global()

        assert moved == 1
        assert paths.uses_v41_layout
        assert (tmp_path / "_global" / "calculator" / "SKILL.md").exists()
        assert not legacy.exists()


class TestSkillRegistryTenantFilter:
    def test_list_for_tenant(self):
        from tars.skills.registry import SkillRegistry
        from tars.skills.base import Skill, SkillType

        reg = SkillRegistry()
        reg.register(Skill(
            id="global-skill", name="Global", description="",
            type=SkillType.PROMPT, scope="global", tenant_id="global",
        ))
        reg.register(Skill(
            id="private-skill", name="Private", description="",
            type=SkillType.PROMPT, scope="tenant", tenant_id="user-a",
        ))
        reg.register(Skill(
            id="other-skill", name="Other", description="",
            type=SkillType.PROMPT, scope="tenant", tenant_id="user-b",
        ))

        visible_a = {s.id for s in reg.list_for_tenant("user-a")}
        assert visible_a == {"global-skill", "private-skill"}

        visible_b = {s.id for s in reg.list_for_tenant("user-b")}
        assert visible_b == {"global-skill", "other-skill"}

    def test_get_prefers_tenant_override(self):
        from tars.skills.registry import SkillRegistry
        from tars.skills.base import Skill, SkillType

        reg = SkillRegistry()
        reg.register(Skill(
            id="pdf", name="Global PDF", description="",
            type=SkillType.PROMPT, scope="global", tenant_id="global",
        ))
        reg.register(Skill(
            id="pdf", name="Tenant PDF", description="",
            type=SkillType.PROMPT, scope="tenant", tenant_id="user-a",
        ))

        assert reg.get("pdf", "user-a").name == "Tenant PDF"
        assert reg.get("pdf", "user-b").name == "Global PDF"


class TestSkillLoaderTenant:
    def test_load_global_and_tenant_dirs(self, tmp_path):
        from tars.skills.loader import SkillLoader
        from tars.skills.registry import SkillRegistry

        global_dir = tmp_path / "_global" / "alpha"
        global_dir.mkdir(parents=True)
        (global_dir / "SKILL.md").write_text(
            "---\nname: alpha\ndescription: global alpha\n---\nAlpha body",
            encoding="utf-8",
        )

        tenant_dir = tmp_path / "tenants" / "user-x" / "beta"
        tenant_dir.mkdir(parents=True)
        (tenant_dir / "SKILL.md").write_text(
            "---\nname: beta\ndescription: tenant beta\n---\nBeta body",
            encoding="utf-8",
        )

        reg = SkillRegistry()
        loader = SkillLoader(str(tmp_path), skill_registry=reg)
        loaded = loader.load_all()

        assert len(loaded) == 2
        by_id = {s.id: s for s in loaded}
        assert by_id["alpha"].scope == "global"
        assert by_id["beta"].scope == "tenant"
        assert by_id["beta"].tenant_id == "user-x"

        visible = {s.id for s in reg.list_for_tenant("user-x")}
        assert visible == {"alpha", "beta"}


class TestSkillInstallerTenant:
    @pytest.mark.asyncio
    async def test_install_to_tenant_dir(self, tmp_path):
        from tars.skillhub.installer import SkillInstaller
        from tars.skillhub.client import SkillHubClient
        from tars.skills.loader import SkillLoader
        from tars.skills.registry import SkillRegistry

        bundle = tmp_path / "bundle.md"
        bundle.write_text(
            "---\nname: demo-skill\ndescription: demo\npermissions: []\n---\nDemo prompt",
            encoding="utf-8",
        )

        skills_root = tmp_path / "skills"
        reg = SkillRegistry()
        loader = SkillLoader(str(skills_root), skill_registry=reg)

        from tars.skillhub.local_catalog import LocalSkillCatalog

        catalog = LocalSkillCatalog(
            catalog_path=str(tmp_path / "catalog.json"),
            bundle_dir=str(tmp_path),
            package_dir=str(skills_root / "_global"),
        )
        catalog_path = tmp_path / "catalog.json"
        catalog_path.write_text(json.dumps([{
            "id": "bundled/demo-skill",
            "name": "demo-skill",
            "description": "demo",
            "type": "prompt",
            "source": "bundled",
            "bundle_file": "bundle.md",
        }]), encoding="utf-8")

        installer = SkillInstaller(
            skills_dir=str(skills_root),
            client=SkillHubClient(),
            skill_loader=loader,
            skill_registry=reg,
            local_catalog=catalog,
        )

        result = await installer.install(
            "bundled/demo-skill",
            confirm_permissions=False,
            skip_dependency_check=True,
            scope="tenant",
            tenant_id="user-1",
        )

        assert result["success"] is True
        target = skills_root / "tenants" / "user-1" / "demo-skill"
        assert target.exists()
        assert (target / "SKILL.md").exists()

        visible_user1 = reg.list_for_tenant("user-1")
        visible_user2 = reg.list_for_tenant("user-2")
        assert any(s.id == "demo-skill" for s in visible_user1)
        assert not any(s.id == "demo-skill" for s in visible_user2)


class TestSkillRouterTenant:
    def test_route_respects_tenant_visibility(self):
        from tars.skills.router import SkillRouter
        from tars.skills.registry import SkillRegistry
        from tars.skills.base import Skill, SkillType
        from tars.config.skills import SkillsConfig

        reg = SkillRegistry()
        reg.register(Skill(
            id="pdf", name="pdf", description="PDF toolkit",
            type=SkillType.PROMPT, prompt_template="global",
            enabled=True, scope="global", tenant_id="global", tags=["pdf"],
        ))
        reg.register(Skill(
            id="pdf", name="pdf", description="Tenant PDF only",
            type=SkillType.PROMPT, prompt_template="tenant",
            enabled=True, scope="tenant", tenant_id="user-a", tags=["pdf"],
        ))

        router = SkillRouter(reg, SkillsConfig())
        matched_a = router.route_from_content("帮我处理 PDF", tenant_id="user-a")
        matched_b = router.route_from_content("帮我处理 PDF", tenant_id="user-b")

        assert matched_a[0][0].prompt_template == "tenant"
        assert matched_b[0][0].prompt_template == "global"
