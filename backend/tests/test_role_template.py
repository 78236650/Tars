"""v4.0.2 角色模板测试"""
import pytest
from tars.database import Database
from tars.gateway.role_template import RoleTemplateManager


@pytest.fixture
def manager(tmp_path):
    db = Database(db_path=str(tmp_path / "test.db"))
    return RoleTemplateManager(db)


class TestRoleTemplateManager:
    def test_builtins_seeded(self, manager):
        templates = manager.list_templates()
        ids = [t.id for t in templates]
        assert "admin" in ids
        assert "developer" in ids
        assert "analyst" in ids
        assert "operator" in ids
        assert "standard" in ids
        assert "readonly" in ids

    def test_get_template(self, manager):
        t = manager.get_template("developer")
        assert t.name == "开发者"
        assert t.is_builtin is True
        assert "shell" in t.allowed_tools

    def test_admin_all_tools(self, manager):
        t = manager.get_template("admin")
        assert t.allowed_tools == "*"

    def test_create_custom(self, manager):
        t = manager.create_template(
            id="custom1", name="自定义角色",
            allowed_tools=["weather", "web_search"],
            allowed_modules=["knowledge"],
        )
        assert t.id == "custom1"
        assert t.is_builtin is False
        assert t.allowed_tools == ["weather", "web_search"]

    def test_update_custom(self, manager):
        manager.create_template(id="custom2", name="Test")
        ok = manager.update_template("custom2", name="Updated", allowed_tools=["shell"])
        assert ok is True
        t = manager.get_template("custom2")
        assert t.name == "Updated"
        assert t.allowed_tools == ["shell"]

    def test_cannot_update_builtin(self, manager):
        ok = manager.update_template("admin", name="Hacked")
        assert ok is False

    def test_delete_custom(self, manager):
        manager.create_template(id="custom3", name="ToDelete")
        ok = manager.delete_template("custom3")
        assert ok is True
        assert manager.get_template("custom3") is None

    def test_cannot_delete_builtin(self, manager):
        ok = manager.delete_template("admin")
        assert ok is False

    def test_can_use_tool_admin(self, manager):
        assert manager.can_use_tool("admin", "anything") is True

    def test_can_use_tool_standard(self, manager):
        assert manager.can_use_tool("standard", "weather") is True
        assert manager.can_use_tool("standard", "shell") is False

    def test_can_access_module(self, manager):
        assert manager.can_access_module("analyst", "bi") is True
        assert manager.can_access_module("analyst", "meeting") is False

    def test_get_user_permissions(self, manager):
        perms = manager.get_user_permissions("developer")
        assert perms["role_template_id"] == "developer"
        assert "shell" in perms["allowed_tools"]
        assert "bi" in perms["allowed_modules"]

    def test_duplicate_create_fails(self, manager):
        manager.create_template(id="dup", name="First")
        with pytest.raises(Exception):
            manager.create_template(id="dup", name="Second")
