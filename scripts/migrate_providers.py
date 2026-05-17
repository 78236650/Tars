#!/usr/bin/env python3
"""Auto-generate providers.yaml from existing environment variables.

Usage:
    python scripts/migrate_providers.py
"""
import os
import yaml
from pathlib import Path


def migrate():
    providers = {}

    # Ollama (always present)
    providers["ollama-local"] = {
        "type": "ollama",
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "default_model": os.getenv("OLLAMA_MODEL", "llama3.2"),
        "display_name": "Ollama (本地)",
    }

    # DeepSeek
    if os.getenv("DEEPSEEK_API_KEY"):
        providers["deepseek"] = {
            "type": "openai_compat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "${DEEPSEEK_API_KEY}",
            "default_model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            "display_name": "DeepSeek",
        }

    # DashScope (Alibaba Qwen)
    if os.getenv("DASHSCOPE_API_KEY"):
        providers["qwen"] = {
            "type": "openai_compat",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "${DASHSCOPE_API_KEY}",
            "default_model": os.getenv("DASHSCOPE_MODEL", "qwen-max"),
            "display_name": "Qwen (阿里云)",
            "quirks": {"tool_call_nested": True},
        }

    # OpenRouter
    if os.getenv("OPENROUTER_API_KEY"):
        providers["openrouter"] = {
            "type": "openai_compat",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "${OPENROUTER_API_KEY}",
            "default_model": os.getenv("OPENROUTER_MODEL", ""),
            "display_name": "OpenRouter",
        }

    config = {
        "default_provider": "ollama-local",
        "providers": providers,
    }

    output = Path(__file__).resolve().parent.parent / "backend" / "config" / "providers.yaml"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    print(f"Generated {output}")
    print(f"  {len(providers)} provider(s) configured")


if __name__ == "__main__":
    migrate()
