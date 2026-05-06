# TARS OpenRouter Provider
# Layer 4: OpenRouter 实现

import os
import httpx
from typing import List, AsyncGenerator
from .base import LLMProvider, ChatMessage, ModelResponse
from dotenv import load_dotenv

load_dotenv()


class OpenRouterProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, default_model: str | None = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.base_url = "https://openrouter.ai/api/v1"
        self.default_model = default_model or "openai/gpt-4o-mini"
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
    ) -> ModelResponse | AsyncGenerator[str, None]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://tars.ai",
            "X-Title": "TARS AI Agent"
        }

        formatted_messages = []
        for msg in messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            if msg.name:
                msg_dict["name"] = msg.name
            formatted_messages.append(msg_dict)

        payload = {
            "model": model or self.default_model,
            "messages": formatted_messages,
            "temperature": temperature,
            "stream": stream
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if tools:
            payload["tools"] = tools

        if not stream:
            # 非流式响应
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            return ModelResponse(
                content=data["choices"][0]["message"]["content"],
                model=data["model"],
                usage=data.get("usage")
            )
        else:
            # 流式响应生成器
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
