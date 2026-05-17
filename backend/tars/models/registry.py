"""Provider Registry — v4.0.0.

Discovers and manages LLM provider plugins.
Supports: builtin plugins, config-driven discovery, hot-reload.
"""
from typing import Dict, Optional, Type

from .base import ProviderBase


class ProviderRegistry:
    """Registry for LLM provider plugins.

    Builtin types: ollama, openai_compat.
    Extensible: call register() to add custom providers.
    """

    def __init__(self):
        self._types: Dict[str, Type[ProviderBase]] = {}
        self._instances: Dict[str, ProviderBase] = {}
        self._register_builtins()

    def _register_builtins(self):
        from .plugins.ollama import OllamaProvider
        from .plugins.openai_compat import OpenAICompatProvider
        self.register("ollama", OllamaProvider)
        self.register("openai_compat", OpenAICompatProvider)

    def register(self, name: str, provider_cls: Type[ProviderBase]):
        self._types[name] = provider_cls

    def unregister(self, name: str):
        self._types.pop(name, None)
        self._instances.pop(name, None)

    def get_type(self, name: str) -> Optional[Type[ProviderBase]]:
        return self._types.get(name)

    def get_instance(self, name: str, config: dict = None) -> Optional[ProviderBase]:
        """Get or create a provider instance by type name."""
        prov = self._instances.get(name)
        if prov and not config:
            return prov

        cls = self._types.get(name)
        if not cls:
            return None

        if config is None:
            config = {}

        instance = cls(**config)
        self._instances[name] = instance
        return instance

    def list_types(self) -> list[dict]:
        return [
            {
                "name": cls.name,
                "display_name": cls.display_name,
                "auth_type": cls.auth_type,
                "supports_tools": cls.supports_tools,
                "supports_vision": cls.supports_vision,
            }
            for cls in self._types.values()
        ]

    def list_providers(self) -> list[dict]:
        return [
            {
                "name": cls.name,
                "display_name": cls.display_name,
                "auth_type": cls.auth_type,
                "supports_tools": cls.supports_tools,
            }
            for cls in self._types.values()
        ]


# ── Global singleton ────────────────────────────────────────────────

provider_registry = ProviderRegistry()
