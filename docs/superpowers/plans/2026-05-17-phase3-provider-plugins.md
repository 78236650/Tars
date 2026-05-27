---
doc_type: plan
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# Phase 3: Provider Plugin Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor TARS LLM provider layer into a plugin architecture — unified interface, config-driven, hot-swappable, user-extensible.

**Architecture:** `ProviderBase` abstract class defines the contract. `ProviderRegistry` discovers and manages instances. Existing providers migrate to `models/plugins/` directory. New `providers.yaml` config replaces hardcoded setup.

**Tech Stack:** Python 3.8+, httpx, ABC, YAML config, dynamic import

**Dependencies:** Phase 2 connection pool (`backend/tars/models/connection_pool.py`)

---

## File Structure

```
backend/tars/models/
├── base.py              # ProviderBase ABC + ChatResponse/ModelInfo dataclasses
├── registry.py          # ProviderRegistry (discover + instantiate + hot-reload)
├── connection_pool.py   # (from Phase 2)
├── config.py            # existing model config router (keep)
├── plugins/
│   ├── __init__.py
│   ├── ollama.py        # OllamaProvider (migrated)
│   └── openai_compat.py # OpenAICompatProvider (merged custom + openrouter)
├── __init__.py          # backward-compatible exports
└── _legacy.py           # old imports redirect (temporary)

config/
└── providers.yaml       # Provider configuration

scripts/
└── migrate_providers.py # Auto-generate providers.yaml from env vars

backend/tests/
├── test_provider_base.py
└── test_provider_registry.py
```

---

## Task 1: ProviderBase — 抽象基类

**Files:**
- Modify: `backend/tars/models/base.py`
- Create: `backend/tests/test_provider_base.py`

- [ ] **Step 1: Write failing tests for base interface**

```python
# backend/tests/test_provider_base.py
import pytest
from tars.models.base import ProviderBase, ChatResponse, ModelInfo

class TestProviderBase:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            ProviderBase()

    def test_chat_response_dataclass(self):
        r = ChatResponse(content="hello", model="qwen3")
        assert r.content == "hello"
        assert r.tool_calls is None
        assert r.usage is None

    def test_chat_response_with_tools(self):
        r = ChatResponse(content="", tool_calls=[{"name": "weather", "arguments": {}}], model="qwen3")
        assert len(r.tool_calls) == 1

    def test_model_info_dataclass(self):
        m = ModelInfo(id="qwen3:8b", name="Qwen3 8B", supports_tools=True, context_length=32768)
        assert m.supports_tools is True
        assert m.supports_vision is False

    def test_concrete_provider_must_implement_methods(self):
        class IncompleteProvider(ProviderBase):
            name = "test"
            display_name = "Test"
            auth_type = "none"
        with pytest.raises(TypeError):
            IncompleteProvider()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_provider_base.py -v`
Expected: FAIL (ProviderBase not yet abstract)

- [ ] **Step 3: Implement ProviderBase**

```python
# backend/tars/models/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

@dataclass
class ModelInfo:
    id: str
    name: str
    supports_tools: bool = False
    supports_vision: bool = False
    context_length: int = 4096

@dataclass
class ChatResponse:
    content: str
    model: str = ""
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: Optional[Dict[str, int]] = None

@dataclass
class ChatMessage:
    role: str
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None

class ProviderBase(ABC):
    """Abstract base for all LLM providers."""
    name: str = ""
    display_name: str = ""
    auth_type: str = "none"  # "none" | "api_key"

    @abstractmethod
    async def chat(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> ChatResponse:
        ...

    @abstractmethod
    async def stream_chat(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> AsyncIterator:
        ...

    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        ...

    def supports_tools(self, model: str) -> bool:
        return False

    def supports_vision(self, model: str) -> bool:
        return False

# Backward compatibility aliases
LLMProvider = ProviderBase
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_provider_base.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/tars/models/base.py backend/tests/test_provider_base.py
git commit -m "feat(provider): define ProviderBase ABC with ChatResponse and ModelInfo"
```

---

## Task 2: Migrate OllamaProvider to Plugin

**Files:**
- Create: `backend/tars/models/plugins/__init__.py`
- Create: `backend/tars/models/plugins/ollama.py`
- Modify: `backend/tars/models/ollama.py` (keep as redirect)

- [ ] **Step 1: Create plugins package**

```python
# backend/tars/models/plugins/__init__.py
```

- [ ] **Step 2: Migrate Ollama provider**

Copy `backend/tars/models/ollama.py` to `backend/tars/models/plugins/ollama.py` and refactor to extend `ProviderBase`:

```python
# backend/tars/models/plugins/ollama.py
import json
from typing import AsyncIterator, Dict, List, Optional
from ..base import ProviderBase, ChatResponse, ModelInfo
from ..connection_pool import connection_pool

__provider_class__ = "OllamaProvider"

class OllamaProvider(ProviderBase):
    name = "ollama"
    display_name = "Ollama (Local)"
    auth_type = "none"

    def __init__(self, model: str = "qwen3:8b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._pool_key = f"ollama:{self.base_url}"

    @property
    def client(self):
        return connection_pool.get_client(self._pool_key)

    async def chat(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> ChatResponse:
        payload = {"model": self.model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools
        response = await self.client.post(f"{self.base_url}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        msg = data.get("message", {})
        return ChatResponse(
            content=msg.get("content", ""),
            model=self.model,
            tool_calls=msg.get("tool_calls"),
            usage=data.get("usage"),
        )

    async def stream_chat(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> AsyncIterator:
        payload = {"model": self.model, "messages": messages, "stream": True}
        if tools:
            payload["tools"] = tools
            payload["stream"] = False  # tools require non-stream
        async with self.client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
            async for line in resp.aiter_lines():
                if line:
                    yield json.loads(line)

    async def list_models(self) -> List[ModelInfo]:
        response = await self.client.get(f"{self.base_url}/api/tags")
        response.raise_for_status()
        models = response.json().get("models", [])
        return [ModelInfo(id=m["name"], name=m["name"],
                         supports_tools=self._model_supports_tools(m["name"]))
                for m in models]

    def supports_tools(self, model: str) -> bool:
        return self._model_supports_tools(model)

    def _model_supports_tools(self, model: str) -> bool:
        tool_models = ["qwen3", "qwen2.5", "qwen2", "llama3.1", "llama3.2", "llama3.3", "mistral", "mixtral", "deepseek"]
        return any(t in model.lower() for t in tool_models)

    def supports_vision(self, model: str) -> bool:
        vision_models = ["llava", "bakllava", "llama3.2-vision", "minicpm-v", "qwen2-vl"]
        return any(v in model.lower() for v in vision_models)
```

- [ ] **Step 3: Make old ollama.py a redirect**

```python
# backend/tars/models/ollama.py
# Backward compatibility redirect
from .plugins.ollama import OllamaProvider

__all__ = ["OllamaProvider"]
```

- [ ] **Step 4: Run existing tests for regression**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/ -v --tb=short -k "not test_provider"`
Expected: All pass (imports still work)

- [ ] **Step 5: Commit**

```bash
git add backend/tars/models/plugins/__init__.py backend/tars/models/plugins/ollama.py backend/tars/models/ollama.py
git commit -m "feat(provider): migrate OllamaProvider to plugins directory"
```

---

## Task 3: OpenAI Compatible Provider — 合并 custom + openrouter

**Files:**
- Create: `backend/tars/models/plugins/openai_compat.py`
- Modify: `backend/tars/models/custom.py` (redirect)
- Modify: `backend/tars/models/openrouter.py` (redirect)

- [ ] **Step 1: Implement OpenAICompatProvider**

```python
# backend/tars/models/plugins/openai_compat.py
import json
from typing import AsyncIterator, Dict, List, Optional
from ..base import ProviderBase, ChatResponse, ModelInfo
from ..connection_pool import connection_pool

__provider_class__ = "OpenAICompatProvider"

class OpenAICompatProvider(ProviderBase):
    name = "openai_compat"
    display_name = "OpenAI Compatible"
    auth_type = "api_key"

    def __init__(self, base_url: str, api_key: str = "", model: str = "",
                 display_name: str = "OpenAI Compatible", quirks: Dict = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.display_name = display_name
        self._quirks = quirks or {}
        self._pool_key = f"openai_compat:{self.base_url}"

    @property
    def client(self):
        return connection_pool.get_client(self._pool_key)

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def chat(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> ChatResponse:
        payload = {"model": kwargs.get("model", self.model), "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools
            if self._quirks.get("no_stream_tools"):
                payload["stream"] = False

        response = await self.client.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload, headers=self._headers(),
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]["message"]

        tool_calls = choice.get("tool_calls")
        if tool_calls and self._quirks.get("tool_call_nested"):
            tool_calls = self._flatten_tool_calls(tool_calls)

        return ChatResponse(
            content=choice.get("content", "") or "",
            model=data.get("model", self.model),
            tool_calls=tool_calls,
            usage=data.get("usage"),
        )

    async def stream_chat(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> AsyncIterator:
        payload = {"model": kwargs.get("model", self.model), "messages": messages, "stream": True}
        if tools:
            payload["tools"] = tools
            payload["stream"] = False  # Most providers don't support streaming with tools

        async with self.client.stream(
            "POST", f"{self.base_url}/v1/chat/completions",
            json=payload, headers=self._headers(),
        ) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    chunk = line[6:]
                    if chunk.strip() == "[DONE]":
                        break
                    yield json.loads(chunk)

    async def list_models(self) -> List[ModelInfo]:
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/models", headers=self._headers(),
            )
            response.raise_for_status()
            models = response.json().get("data", [])
            return [ModelInfo(id=m["id"], name=m.get("id", "")) for m in models]
        except Exception:
            return [ModelInfo(id=self.model, name=self.model)] if self.model else []

    def supports_tools(self, model: str) -> bool:
        tool_models = ["qwen-max", "qwen-plus", "qwen-turbo", "deepseek-chat", "kimi",
                       "gpt-4", "gpt-3.5", "claude"]
        return any(t in model.lower() for t in tool_models)

    def _flatten_tool_calls(self, tool_calls: list) -> list:
        """Flatten nested tool_calls format (e.g., Alibaba DashScope)."""
        flattened = []
        for tc in tool_calls:
            fn = tc.get("function", tc)
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    pass
            flattened.append({
                "id": tc.get("id", f"call_{fn.get('name', 'unknown')}"),
                "name": fn.get("name", ""),
                "arguments": args,
            })
        return flattened
```

- [ ] **Step 2: Redirect old modules**

```python
# backend/tars/models/custom.py
from .plugins.openai_compat import OpenAICompatProvider
CustomProvider = OpenAICompatProvider
__all__ = ["CustomProvider", "OpenAICompatProvider"]
```

```python
# backend/tars/models/openrouter.py
from .plugins.openai_compat import OpenAICompatProvider
OpenRouterProvider = OpenAICompatProvider
__all__ = ["OpenRouterProvider", "OpenAICompatProvider"]
```

- [ ] **Step 3: Run tests for regression**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/tars/models/plugins/openai_compat.py backend/tars/models/custom.py backend/tars/models/openrouter.py
git commit -m "feat(provider): implement OpenAICompatProvider merging custom and openrouter"
```

---

## Task 4: ProviderRegistry — 发现与注册

**Files:**
- Create: `backend/tars/models/registry.py`
- Create: `backend/tests/test_provider_registry.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_provider_registry.py
import pytest
from tars.models.registry import ProviderRegistry

class TestProviderRegistry:
    def setup_method(self):
        self.registry = ProviderRegistry()

    def test_discover_builtin_plugins(self):
        self.registry.discover()
        providers = self.registry.list_providers()
        names = [p["name"] for p in providers]
        assert "ollama" in names
        assert "openai_compat" in names

    def test_get_instance_ollama(self):
        self.registry.discover()
        instance = self.registry.get_instance("ollama", {"base_url": "http://localhost:11434", "model": "qwen3:8b"})
        assert instance is not None
        assert instance.name == "ollama"

    def test_get_instance_openai_compat(self):
        self.registry.discover()
        instance = self.registry.get_instance("openai_compat", {
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "test-key",
            "model": "deepseek-chat",
        })
        assert instance is not None
        assert instance.base_url == "https://api.deepseek.com/v1"

    def test_get_unknown_provider_raises(self):
        self.registry.discover()
        with pytest.raises(KeyError):
            self.registry.get_instance("nonexistent", {})

    def test_list_providers_has_metadata(self):
        self.registry.discover()
        providers = self.registry.list_providers()
        for p in providers:
            assert "name" in p
            assert "display_name" in p
            assert "auth_type" in p
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_provider_registry.py -v`
Expected: FAIL (import error)

- [ ] **Step 3: Implement ProviderRegistry**

```python
# backend/tars/models/registry.py
import importlib
import os
from pathlib import Path
from typing import Dict, List, Optional
from .base import ProviderBase

class ProviderRegistry:
    def __init__(self):
        self._classes: Dict[str, type] = {}
        self._instances: Dict[str, ProviderBase] = {}

    def discover(self):
        """Scan plugins directory and user providers."""
        # 1. Built-in plugins
        plugins_dir = Path(__file__).parent / "plugins"
        self._scan_directory(plugins_dir, "tars.models.plugins")

        # 2. User custom providers
        user_dir = Path.home() / ".tars" / "providers"
        if user_dir.exists():
            self._scan_directory(user_dir, None)

    def _scan_directory(self, directory: Path, package_prefix: Optional[str]):
        for f in directory.glob("*.py"):
            if f.name.startswith("_"):
                continue
            module_name = f.stem
            try:
                if package_prefix:
                    module = importlib.import_module(f"{package_prefix}.{module_name}")
                else:
                    spec = importlib.util.spec_from_file_location(module_name, f)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                class_name = getattr(module, "__provider_class__", None)
                if class_name:
                    cls = getattr(module, class_name)
                    if issubclass(cls, ProviderBase):
                        self._classes[cls.name] = cls
            except Exception as e:
                print(f"[ProviderRegistry] Failed to load {f}: {e}")

    def list_providers(self) -> List[Dict]:
        return [
            {"name": cls.name, "display_name": cls.display_name, "auth_type": cls.auth_type}
            for cls in self._classes.values()
        ]

    def get_instance(self, name: str, config: dict) -> ProviderBase:
        if name not in self._classes:
            raise KeyError(f"Provider '{name}' not found. Available: {list(self._classes.keys())}")
        cls = self._classes[name]
        return cls(**config)

    def hot_reload(self, name: str):
        """Re-import a provider module."""
        if name in self._classes:
            del self._classes[name]
        self.discover()

# Global singleton
provider_registry = ProviderRegistry()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_provider_registry.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/tars/models/registry.py backend/tests/test_provider_registry.py
git commit -m "feat(provider): implement ProviderRegistry with plugin discovery"
```

---

## Task 5: providers.yaml — 配置化

**Files:**
- Create: `config/providers.yaml`
- Create: `scripts/migrate_providers.py`

- [ ] **Step 1: Create default providers.yaml**

```yaml
# config/providers.yaml
providers:
  - name: ollama-local
    type: ollama
    base_url: http://localhost:11434
    default_model: qwen3:8b

# Uncomment and configure as needed:
#  - name: aliyun-dashscope
#    type: openai_compat
#    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
#    api_key: ${DASHSCOPE_API_KEY}
#    default_model: qwen-max
#    quirks:
#      tool_call_nested: true
#
#  - name: deepseek
#    type: openai_compat
#    base_url: https://api.deepseek.com/v1
#    api_key: ${DEEPSEEK_API_KEY}
#    default_model: deepseek-chat

default_provider: ollama-local
```

- [ ] **Step 2: Create migration script**

```python
# scripts/migrate_providers.py
"""Auto-generate providers.yaml from existing environment variables."""
import os
import yaml
from pathlib import Path

def migrate():
    providers = []

    # Ollama (always present)
    providers.append({
        "name": "ollama-local",
        "type": "ollama",
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "default_model": os.getenv("OLLAMA_MODEL", "qwen3:8b"),
    })

    # OpenRouter
    if os.getenv("OPENROUTER_API_KEY"):
        providers.append({
            "name": "openrouter",
            "type": "openai_compat",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "${OPENROUTER_API_KEY}",
            "default_model": os.getenv("OPENROUTER_MODEL", ""),
        })

    # DashScope (Alibaba)
    if os.getenv("DASHSCOPE_API_KEY"):
        providers.append({
            "name": "aliyun-dashscope",
            "type": "openai_compat",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "${DASHSCOPE_API_KEY}",
            "default_model": os.getenv("DASHSCOPE_MODEL", "qwen-max"),
            "quirks": {"tool_call_nested": True},
        })

    config = {"providers": providers, "default_provider": "ollama-local"}
    output = Path(__file__).parent.parent / "config" / "providers.yaml"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    print(f"Generated {output}")

if __name__ == "__main__":
    migrate()
```

- [ ] **Step 3: Commit**

```bash
git add config/providers.yaml scripts/migrate_providers.py
git commit -m "feat(provider): add providers.yaml config and migration script"
```

---

## Task 6: Load Config and Wire into Agent

**Files:**
- Modify: `backend/tars/main.py`
- Modify: `backend/tars/models/__init__.py`

- [ ] **Step 1: Add config loader to models/__init__.py**

```python
# backend/tars/models/__init__.py
import os
import yaml
from pathlib import Path
from .base import ProviderBase, ChatResponse, ChatMessage, ModelInfo, LLMProvider
from .registry import ProviderRegistry, provider_registry
from .plugins.ollama import OllamaProvider
from .plugins.openai_compat import OpenAICompatProvider

def load_providers_from_config() -> dict:
    """Load providers.yaml and instantiate configured providers."""
    config_path = Path(__file__).parent.parent.parent / "config" / "providers.yaml"
    if not config_path.exists():
        return {"default": OllamaProvider()}

    with open(config_path) as f:
        config = yaml.safe_load(f)

    provider_registry.discover()
    instances = {}

    for p in config.get("providers", []):
        ptype = p.get("type", "ollama")
        pname = p.get("name", ptype)
        # Resolve env vars in api_key
        api_key = p.get("api_key", "")
        if api_key.startswith("${") and api_key.endswith("}"):
            api_key = os.getenv(api_key[2:-1], "")

        provider_config = {
            "model": p.get("default_model", ""),
            "base_url": p.get("base_url", ""),
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

    default_name = config.get("default_provider", "ollama-local")
    instances["_default"] = instances.get(default_name, list(instances.values())[0] if instances else OllamaProvider())
    return instances

__all__ = [
    "ProviderBase", "LLMProvider", "ChatResponse", "ChatMessage", "ModelInfo",
    "OllamaProvider", "OpenAICompatProvider",
    "ProviderRegistry", "provider_registry",
    "load_providers_from_config",
]
```

- [ ] **Step 2: Wire into main.py startup**

In `backend/tars/main.py`, replace hardcoded provider creation:

```python
from tars.models import load_providers_from_config

# Replace:
#   provider = OllamaProvider(model=...)
# With:
providers = load_providers_from_config()
default_provider = providers["_default"]
```

- [ ] **Step 3: Add provider list API endpoint**

In `backend/tars/main.py` or a new route:

```python
@app.get("/api/providers")
async def list_providers():
    from tars.models import provider_registry
    return provider_registry.list_providers()

@app.post("/api/providers/{name}/test")
async def test_provider(name: str):
    try:
        instance = providers.get(name)
        if not instance:
            return {"status": "error", "message": f"Provider {name} not configured"}
        models = await instance.list_models()
        return {"status": "ok", "models_count": len(models)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 4: Run tests for regression**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/tars/models/__init__.py backend/tars/main.py
git commit -m "feat(provider): wire config-driven provider loading into startup"
```

---

## Task 7: Hot Switch + Final Verification

**Files:**
- Modify: `backend/tars/agent/agent.py`

- [ ] **Step 1: Update agent model switching to use registry**

In `backend/tars/agent/agent.py`, update `switch_model`:

```python
def switch_model(self, model_name: str, provider_name: str = None) -> bool:
    try:
        if provider_name:
            from ..models import providers
            provider = providers.get(provider_name)
            if provider:
                self.provider = provider
                self.current_model = model_name
                self.dispatcher.set_provider(self.provider)
                return True
        # Fallback: just switch model on current provider
        self.provider.model = model_name
        self.current_model = model_name
        return True
    except Exception:
        return False
```

- [ ] **Step 2: Run full test suite**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_provider_base.py tests/test_provider_registry.py -v`
Expected: ALL PASS (10 tests)

- [ ] **Step 3: Run regression**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/ -v --tb=short`
Expected: No regressions

- [ ] **Step 4: Commit**

```bash
git add backend/tars/agent/agent.py
git commit -m "feat(provider): support hot-switching providers via registry"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | ProviderBase ABC | 5 |
| 2 | Ollama plugin migration | — |
| 3 | OpenAI compat provider | — |
| 4 | ProviderRegistry | 5 |
| 5 | providers.yaml + migration | — |
| 6 | Config loading + wiring | — |
| 7 | Hot switch + verification | — |
| **Total** | | **10+** |
