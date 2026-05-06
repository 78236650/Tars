"""TARS Ollama Provider - 支持 Function Calling"""
import os
import json
import httpx
from typing import List, AsyncGenerator, Optional
from .base import LLMProvider, ChatMessage, ModelResponse


class OllamaProvider(LLMProvider):
    """Ollama 本地模型 Provider，支持 function calling"""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.2")
        self.client = httpx.AsyncClient(timeout=120.0)

    async def chat(
        self,
        messages: List[ChatMessage],
        stream: bool = False,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: Optional[List[dict]] = None,
    ):
        url = f"{self.base_url}/api/chat"
        target_model = model or self.model

        formatted_messages = []
        for msg in messages:
            m = {"role": msg.role, "content": msg.content or ""}
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
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

        if tools:
            payload["tools"] = tools
            payload["stream"] = False  # function calling 下禁用流式

        if not payload["stream"]:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            msg = data.get("message", {})
            content = msg.get("content", "") or ""
            tool_calls = msg.get("tool_calls")

            if tool_calls:
                # 返回工具调用信息
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
                usage={"prompt_eval_count": data.get("prompt_eval_count", 0), "eval_count": data.get("eval_count", 0)},
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
            return []
