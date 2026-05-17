"""Tests for Module Registry — v4.0.0 Phase 4."""
import pytest


class TestModuleRegistry:
    """Verify ModuleRegistry loads config and checks enable/disable."""

    def setup_method(self):
        from tars.modules.registry import ModuleRegistry
        self.registry = ModuleRegistry()

    def test_core_modules_always_enabled(self):
        self.registry.load()
        for m in ("auth", "chat", "memory", "skills", "tools", "knowledge"):
            assert self.registry.is_enabled(m) is True

    def test_optional_modules_have_default(self):
        self.registry.load()
        # Without config file, optional modules should be True (default)
        assert self.registry.is_enabled("bi") is True
        assert self.registry.is_enabled("admin") is True

    def test_list_modules(self):
        self.registry.load()
        modules = self.registry.list_modules()
        names = [m["name"] for m in modules]
        assert "auth" in names
        assert "meeting" in names
        assert len(modules) == 10  # 6 core + 4 optional
        for m in modules:
            assert "name" in m
            assert "enabled" in m
            assert "type" in m
            assert m["type"] in ("core", "optional")

    def test_load_config_meeting_disabled(self, tmp_path):
        import yaml
        config_path = tmp_path / "modules.yaml"
        config_path.write_text(yaml.dump({
            "default_enabled": False,
            "modules": {
                "meeting": False,
                "bi": True,
            }
        }))
        self.registry.load(str(config_path))
        assert self.registry.is_enabled("meeting") is False
        assert self.registry.is_enabled("bi") is True

    def test_load_config_bad_yaml_doesnt_crash(self, tmp_path):
        config_path = tmp_path / "modules.yaml"
        config_path.write_text("{{{bad yaml")
        self.registry.load(str(config_path))
        # Should fall through to defaults
        assert self.registry.is_enabled("meeting") is True
