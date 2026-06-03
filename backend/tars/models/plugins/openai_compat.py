"""OpenAI-Compatible Provider Plugin — v4.0.0.

Generic provider for any OpenAI-compatible API (DeepSeek, Qwen, custom endpoints).
Merged from models/custom.py and expanded with provider metadata.
"""
import json
from typing import List, AsyncGenerator, Dict, Any, Union, Optional

from ..base import ProviderBase, ChatMessage, ModelResponse


def _normalize_openai_response(data: dict, default_model: str) -> dict:
    choices = data.get("choices", [])
    if not choices:
        return {"content": data.get("content", ""), "model": data.get("model", default_model)}

    message = choices[0].get("message", {})
    content = message.get("content", "") or ""
    tool_calls = message.get("tool_calls")
    reasoning_content = message.get("reasoning_content")  # DeepSeek 推理模型的推理过程

    result = {"content": content, "model": data.get("model", default_model)}
    if tool_calls:
        result["tool_calls"] = tool_calls
    if reasoning_content:
        result["reasoning_content"] = reasoning_content
    return result


class OpenAICompatProvider(ProviderBase):
    """Generic provider for OpenAI-compatible APIs.

    Supports: DeepSeek, Qwen, local vLLM, LiteLLM proxy, etc.
    """

    name = "openai_compat"
    display_name = "OpenAI Compatible"
    auth_type = "api_key"
    supports_tools = True

    def __init__(
        self,
        base_url: str = "",
        model: str = "",
        api_key: str = "",
        default_model: str = "gpt-3.5-turbo",
        quirks: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model or default_model
        self.api_key = api_key or ""
        self._quirks = quirks or {}

        from ..connection_pool import get_connection_pool
        self._pool = get_connection_pool()

    @property
    def client(self):
        return self._pool.client

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def chat(
        self,
        messages: List[ChatMessage],
        stream: bool = False,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: List[Dict] | None = None,
        response_format: Optional[dict] = None,
        **kwargs,
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        url = f"{self.base_url}/chat/completions"
        target_model = model or self.model

        formatted_messages = []
        for msg in messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            if msg.name:
                msg_dict["name"] = msg.name
            if msg.tool_calls:
                normalized_calls = []
                for tc in msg.tool_calls:
                    tc_copy = dict(tc)
                    func = dict(tc_copy.get("function", {}))
                    args = func.get("arguments")
                    if isinstance(args, dict):
                        func["arguments"] = json.dumps(args, ensure_ascii=False)
                    elif args is None:
                        func["arguments"] = "{}"
                    tc_copy["function"] = func
                    normalized_calls.append(tc_copy)
                msg_dict["tool_calls"] = normalized_calls
            # DeepSeek 推理模型要求将 reasoning_content 传回 API
            if msg.reasoning_content:
                msg_dict["reasoning_content"] = msg.reasoning_content
            formatted_messages.append(msg_dict)

        payload = {
            "model": target_model,
            "messages": formatted_messages,
            "temperature": temperature,
            "stream": stream,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if response_format:
            payload["response_format"] = response_format

        if tools:
            payload["tools"] = tools
            payload["stream"] = False
            stream = False

        if not stream:
            response = await self.client.post(url, headers=self._headers(), json=payload)
            response.raise_for_status()
            data = response.json()
            return _normalize_openai_response(data, target_model)
        else:
            async def generate():
                async with self.client.stream("POST", url, headers=self._headers(), json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            line = line[6:]
                            if line.strip() == "[DONE]":
                                break
                            try:
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
        def _coerce_ids(raw) -> List[str]:
            out: List[str] = []
            if not raw or not isinstance(raw, list):
                return out
            for m in raw:
                if isinstance(m, str):
                    s = m.strip()
                    if s:
                        out.append(s)
                elif isinstance(m, dict):
                    mid = m.get("id") if m.get("id") is not None else m.get("name")
                    if mid is not None:
                        s = str(mid).strip()
                        if s:
                            out.append(s)
                else:
                    s = str(m).strip()
                    if s:
                        out.append(s)
            return out

        try:
            response = await self.client.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and "data" in data:
                    ids = _coerce_ids(data.get("data"))
                    return ids if ids else [self.model]
                if isinstance(data, dict) and "models" in data:
                    ids = _coerce_ids(data.get("models"))
                    return ids if ids else [self.model]
            return [self.model]
        except Exception:
            return [self.model]

    async def test_connection(self) -> tuple[bool, str]:
        import httpx
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                },
                timeout=30.0,
            )
            if response.status_code == 200:
                return True, "连接成功"
            return False, f"连接失败: HTTP {response.status_code}"
        except httpx.TimeoutException:
            return False, "连接超时"
        except Exception as e:
            return False, f"连接失败: {str(e)}"
