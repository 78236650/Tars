# TARS Provider 插件开发指南

## 概述

TARS v4.0.0 采用插件化 Provider 架构。新增 LLM Provider 只需：
1. 编写一个 Python 文件，继承 `ProviderBase`
2. 在 `providers.yaml` 中添加配置

---

## 1. 架构

```
backend/tars/models/
├── base.py              # ProviderBase ABC
├── registry.py          # ProviderRegistry（自动发现 + 实例管理）
├── connection_pool.py   # 共享 httpx 连接池
└── plugins/
    ├── ollama.py        # Ollama 本地模型
    └── openai_compat.py # OpenAI 兼容协议（DeepSeek、通义、Kimi 等）
```

---

## 2. ProviderBase 接口

```python
from abc import ABC, abstractmethod
from typing import List, Dict
from tars.models.base import ProviderBase, ChatMessage, ModelResponse

class MyProvider(ProviderBase):
    # 元信息（必填）
    name = "my_provider"           # 唯一标识，用于 providers.yaml 中的 type
    display_name = "My Provider"   # 前端展示名
    auth_type = "api_key"          # none | api_key
    supports_tools = True          # 是否支持 function calling
    supports_vision = False        # 是否支持图片输入

    @abstractmethod
    async def chat(self, messages, stream=False, model=None,
                   temperature=0.7, tools=None, **kwargs):
        """发送对话请求。stream=True 时返回 AsyncGenerator，否则返回 ModelResponse 或 dict。"""
        ...

    @abstractmethod
    async def list_models(self) -> List[str]:
        """返回可用模型 ID 列表。"""
        ...

    async def test_connection(self) -> tuple[bool, str]:
        """连接测试（可选）。返回 (success, message)。"""
        ...
```

---

## 3. 开发示例：vLLM Provider

```python
# backend/tars/models/plugins/vllm.py
import json
from typing import List, AsyncGenerator
from ..base import ProviderBase, ChatMessage, ModelResponse
from ..connection_pool import get_connection_pool


class VLLMProvider(ProviderBase):
    name = "vllm"
    display_name = "vLLM Local"
    auth_type = "none"
    supports_tools = True

    def __init__(self, base_url: str = "http://localhost:8000", model: str = "", **kwargs):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._pool = get_connection_pool()

    @property
    def client(self):
        return self._pool.client

    async def chat(self, messages, stream=False, model=None, temperature=0.7, tools=None, **kwargs):
        target_model = model or self.model
        payload = {
            "model": target_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools

        if not stream:
            resp = await self.client.post(f"{self.base_url}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]["message"]
            return ModelResponse(content=choice.get("content", ""), model=target_model)
        else:
            async def generate():
                async with self.client.stream("POST", f"{self.base_url}/v1/chat/completions", json=payload) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: ") and line[6:].strip() != "[DONE]":
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0].get("delta", {})
                            if delta.get("content"):
                                yield delta["content"]
            return generate()

    async def list_models(self) -> List[str]:
        resp = await self.client.get(f"{self.base_url}/v1/models")
        resp.raise_for_status()
        return [m["id"] for m in resp.json().get("data", [])]

    async def test_connection(self) -> tuple[bool, str]:
        try:
            models = await self.list_models()
            return True, f"{len(models)} 个模型可用"
        except Exception as e:
            return False, str(e)
```

---

## 4. 注册 Provider

### 方式一：放入 plugins 目录（推荐）

将文件放入 `backend/tars/models/plugins/`，重启后自动发现。

### 方式二：手动注册

```python
from tars.models import provider_registry
from my_module import VLLMProvider

provider_registry.register("vllm", VLLMProvider)
```

---

## 5. 配置 providers.yaml

```yaml
# backend/config/providers.yaml
default_provider: ollama-local

providers:
  ollama-local:
    type: ollama
    base_url: http://localhost:11434
    default_model: qwen3:8b

  deepseek:
    type: openai_compat
    base_url: https://api.deepseek.com/v1
    api_key: "${DEEPSEEK_API_KEY}"
    default_model: deepseek-chat

  my-vllm:
    type: vllm
    base_url: http://gpu-server:8000
    default_model: Qwen/Qwen2.5-72B-Instruct
```

环境变量用 `${VAR_NAME}` 语法引用，启动时自动展开。

---

## 6. API

```
GET  /api/providers              — 列出已注册 Provider 类型
POST /api/providers/{name}/test  — 测试 Provider 连接
```

---

## 7. 连接池

所有 Provider 共享 `connection_pool.py` 提供的 httpx.AsyncClient：

```python
from ..connection_pool import get_connection_pool

pool = get_connection_pool()
client = pool.client  # 共享的 AsyncClient 实例
```

连接池参数可通过环境变量覆盖：
- `TARS_LLM_READ_TIMEOUT` — 读超时（默认 600s，LLM 生成慢）
- `TARS_LLM_CONNECT_TIMEOUT` — 连接超时（默认 30s）

---

*文档版本: v4.0.0 | 更新日期: 2026-05-17*
