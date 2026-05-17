"""Tests for TARS ProviderRegistry — Phase 3 Task 4."""
import pytest
from tars.models.registry import ProviderRegistry, provider_registry


class TestProviderRegistry:
    """Verify provider discovery and instantiation."""

    def test_registry_has_builtins(self):
        types = provider_registry.list_types()
        names = {t["name"] for t in types}
        assert "ollama" in names
        assert "openai_compat" in names

    def test_register_custom_provider(self):
        reg = ProviderRegistry()
        from tars.models.base import ProviderBase, ChatResponse

        class CustomProv(ProviderBase):
            name = "custom_test"
            display_name = "Custom Test"

            async def chat(self, **kw):
                return ChatResponse(content="ok")

            async def list_models(self):
                return ["m1"]

        reg.register("custom_test", CustomProv)
        assert reg.get_type("custom_test") is CustomProv

    def test_get_instance_creates_provider(self):
        reg = ProviderRegistry()
        instance = reg.get_instance("ollama")
        assert instance is not None
        assert instance.name == "ollama"

    def test_get_instance_caches(self):
        reg = ProviderRegistry()
        i1 = reg.get_instance("ollama")
        i2 = reg.get_instance("ollama")
        assert i1 is i2  # Same cached instance

    def test_list_types_returns_metadata(self):
        types = provider_registry.list_types()
        ollama = next(t for t in types if t["name"] == "ollama")
        assert ollama["display_name"] == "Ollama Local"
        assert ollama["supports_tools"] is True
