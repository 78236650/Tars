# TARS Custom Provider
# Layer 4: 自定义 OpenAI 兼容 API Provider

import httpx
from typing import List, AsyncGenerator, Dict, Any, Union
from .base import LLMProvider, ChatMessage, ModelResponse


class CustomProvider(LLMProvider):
    def __init__(self, base_url: str, model: str, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key or ""
        self.client = httpx.AsyncClient(timeout=120.0)

    async def chat(
        self,
        messages: List[ChatMessage],
        stream: bool = False,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: List[Dict] | None = None,
        **kwargs
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        formatted_messages = []
        for msg in messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            if msg.name:
                msg_dict["name"] = msg.name
            formatted_messages.append(msg_dict)

        payload = {
            "model": model or self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "stream": stream
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if tools:
            payload["tools"] = tools

        if not stream:
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data
        else:
            async def generate():
                async with self.client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            line = line[6:]
                            if line.strip() == "[DONE]":
                                break
                            try:
                                import json
                                chunk = json.loads(line)
                                if chunk.get("choices"):
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except Exception:
                                pass

            return generate()

    async def list_models(self) -> List[str]:
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = await self.client.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                if "data" in data:
                    return [m.get("id", m.get("name", str(i))) for i, m in enumerate(data["data"])]
                elif "models" in data:
                    return data["models"]
            return [self.model]
        except Exception:
            return [self.model]

    async def test_connection(self) -> tuple[bool, str]:
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5
                },
                timeout=30.0
            )
            if response.status_code == 200:
                return True, "连接成功"
            return False, f"连接失败: HTTP {response.status_code}"
        except httpx.TimeoutException:
            return False, "连接超时"
        except Exception as e:
            return False, f"连接失败: {str(e)}"
