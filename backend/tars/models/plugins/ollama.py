"""Ollama Provider Plugin — v4.0.0.

Migrated from models/ollama.py. Uses shared connection pool.
"""
import os
import json
from typing import List, AsyncGenerator, Optional

from ..base import ProviderBase, ChatMessage, ModelResponse


class OllamaProvider(ProviderBase):
    """Ollama local model provider with function calling support."""

    name = "ollama"
    display_name = "Ollama Local"
    auth_type = "none"
    supports_tools = True

    def __init__(self, base_url: str | None = None, model: str | None = None,
                 default_model: str = "llama3.2", **kwargs):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", default_model)
        self._default_model = default_model

        # Shared connection pool (Phase 2)
        from ..connection_pool import get_connection_pool
        self._pool = get_connection_pool()

    @property
    def client(self):
        return self._pool.client

    async def chat(
        self,
        messages: List[ChatMessage],
        stream: bool = False,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: Optional[List[dict]] = None,
        response_format: Optional[dict] = None,
        **kwargs,
    ):
        url = f"{self.base_url}/api/chat"
        target_model = model or self.model

        formatted_messages = []
        for msg in messages:
            m = {"role": msg.role, "content": msg.content or ""}
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                normalized_calls = []
                for tc in msg.tool_calls:
                    tc_copy = dict(tc)
                    func = dict(tc_copy.get("function", {}))
                    args = func.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args) if args else {}
                        except (json.JSONDecodeError, TypeError):
                            args = {}
                    func["arguments"] = args
                    tc_copy["function"] = func
                    normalized_calls.append(tc_copy)
                m["tool_calls"] = normalized_calls
            if msg.images:
                m["images"] = msg.images
            formatted_messages.append(m)

        payload = {
            "model": target_model,
            "messages": formatted_messages,
            "stream": stream,
            "options": {"temperature": temperature},
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        if response_format:
            if response_format.get("type") == "json_schema" and response_format.get("schema"):
                payload["format"] = response_format["schema"]
            else:
                payload["format"] = "json"

        if tools:
            payload["tools"] = tools
            payload["stream"] = False

        if not payload["stream"]:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            msg = data.get("message", {})
            content = msg.get("content", "") or ""
            tool_calls = msg.get("tool_calls")

            if tool_calls:
                normalized = []
                for tc in tool_calls:
                    func = tc.get("function", {})
                    args = func.get("arguments", {})
                    if isinstance(args, dict):
                        args = json.dumps(args, ensure_ascii=False)
                    normalized.append({
                        "id": tc.get("id", f"call_{func.get('name', '')}"),
                        "type": "function",
                        "function": {"name": func.get("name", ""), "arguments": args},
                    })
                return {"content": content, "tool_calls": normalized, "model": data.get("model", target_model)}

            return ModelResponse(
                content=content,
                model=data.get("model", target_model),
                usage={"prompt_eval_count": data.get("prompt_eval_count", 0),
                        "eval_count": data.get("eval_count", 0)},
            )
        else:
            async def generate():
                async with self.client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                chunk = json.loads(line)
                                if "message" in chunk and "content" in chunk["message"]:
                                    content = chunk["message"]["content"]
                                    if content:
                                        yield content
                            except Exception:
                                pass
            return generate()

    async def list_models(self) -> List[str]:
        url = f"{self.base_url}/api/tags"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return [self.model]

    async def test_connection(self) -> tuple[bool, str]:
        try:
            models = await self.list_models()
            if models:
                return True, f"连接成功，{len(models)} 个模型可用"
            return False, "未检测到可用模型"
        except Exception as e:
            return False, f"连接失败: {e}"
