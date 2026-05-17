# TARS Model Layer Package (v4.0.0)
# Provider plugin architecture with backward-compat exports.
import os
from pathlib import Path
from typing import Dict

from .base import ProviderBase, LLMProvider, ChatMessage, ChatResponse, ModelResponse, ModelInfo
from .registry import ProviderRegistry, provider_registry

# ── Backward-compat: old top-level imports still work ──────────────
from .plugins.ollama import OllamaProvider as _OllamaPlugin
from .plugins.openai_compat import OpenAICompatProvider as _OpenAICompatPlugin

# Public module-level name
OpenAICompatProvider = _OpenAICompatPlugin

# Legacy name alias
OllamaProvider = _OllamaPlugin
CustomProvider = _OpenAICompatPlugin  # old name → new provider

# ── Config-driven provider loading ─────────────────────────────────

providers: Dict[str, ProviderBase] = {}


def load_providers_from_config(config_path: str = None) -> Dict[str, ProviderBase]:
    """Load provider instances from providers.yaml.

    Returns dict of {name: ProviderBase instance}, with "_default" key
    pointing to the configured default.
    """
    global providers
    import yaml

    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "providers.yaml"

    config = {}
    if os.path.exists(str(config_path)):
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            pass

    instances: Dict[str, ProviderBase] = {}

    for pname, p in config.get("providers", {}).items():
        ptype = p.get("type", pname)
        api_key = os.path.expandvars(p.get("api_key", ""))

        provider_config = {
            "base_url": p.get("base_url", ""),
            "model": p.get("default_model", ""),
            "default_model": p.get("default_model", ""),
        }
        if api_key:
            provider_config["api_key"] = api_key
        if p.get("quirks"):
            provider_config["quirks"] = p["quirks"]
        if p.get("display_name"):
            provider_config["display_name"] = p["display_name"]

        try:
            instances[pname] = provider_registry.get_instance(ptype, provider_config)
        except Exception as e:
            print(f"[Models] Failed to init provider {pname}: {e}")

    # Set default
    default_name = config.get("default_provider", "ollama-local")
    instances["_default"] = instances.get(default_name)
    if not instances["_default"]:
        # Fallback: create bare Ollama
        instances["_default"] = _OllamaPlugin()
    providers.update(instances)
    return instances


__all__ = [
    "ProviderBase", "LLMProvider",
    "ChatMessage", "ChatResponse", "ModelResponse", "ModelInfo",
    "OllamaProvider", "CustomProvider", "OpenAICompatProvider",
    "ProviderRegistry", "provider_registry",
    "providers", "load_providers_from_config",
]
