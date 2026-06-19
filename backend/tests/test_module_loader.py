"""Tests for Module Registry — v4.0.0 Phase 4."""
import pytest


class TestModuleRegistry:
    """Verify ModuleRegistry loads config and checks enable/disable."""

    def setup_method(self):
        from tars.modules.registry import ModuleRegistry
        self.registry = ModuleRegistry()

    def test_core_modules_always_enabled(self):
        self.registry.load()
        for m in ("auth", "chat", "memory", "skills", "tools", "wiki"):
            assert self.registry.is_enabled(m) is True

    def test_optional_modules_have_default(self, tmp_path):
        import yaml
        # 无 optional 段时沿用 default_enabled
        config_path = tmp_path / "modules.yaml"
        config_path.write_text(yaml.dump({"default_enabled": True, "modules": {}}))
        self.registry.load(str(config_path))
        assert self.registry.is_enabled("bi") is True
        assert self.registry.is_enabled("meeting") is True

    def test_list_modules(self):
        self.registry.load()
        modules = self.registry.list_modules()
        names = [m["name"] for m in modules]
        assert "auth" in names
        assert "meeting" in names
        assert "semantic" in names
        assert len(modules) == len(self.registry.CORE_MODULES) + len(self.registry.OPTIONAL_MODULES)
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

    def test_load_config_nested_optional_format(self, tmp_path):
        import yaml
        config_path = tmp_path / "modules.yaml"
        config_path.write_text(
            yaml.dump({
                "modules": {
                    "optional": {
                        "meeting": {"enabled": False},
                        "bi": {"enabled": True},
                    }
                }
            })
        )
        self.registry.load(str(config_path))
        assert self.registry.is_enabled("meeting") is False
        assert self.registry.is_enabled("bi") is True

    def test_load_config_bad_yaml_doesnt_crash(self, tmp_path):
        config_path = tmp_path / "modules.yaml"
        config_path.write_text("{{{bad yaml")
        self.registry.load(str(config_path))
        # Should fall through to defaults
        assert self.registry.is_enabled("meeting") is True
