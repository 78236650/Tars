# TARS Model Layer - Base Provider
# Layer 4: 模型层抽象

from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator
from dataclasses import dataclass


@dataclass
class ChatMessage:
    role: str  # user, assistant, system, tool
    content: str
    tool_call_id: str | None = None
    tool_calls: List[Dict[str, Any]] | None = None  # Ollama native tool calling
    name: str | None = None
    images: List[str] | None = None  # Base64 编码的图片列表（多模态支持）


@dataclass
class ModelResponse:
    content: str
    model: str
    usage: Dict[str, Any] | None = None


class LLMProvider(ABC):
    """LLM Provider 抽象基类"""

    @abstractmethod
    async def chat(
        self,
        messages: List[ChatMessage],
        stream: bool = False,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: List[Dict] | None = None,
        response_format: Dict[str, Any] | None = None,
        **kwargs
    ) -> ModelResponse | AsyncGenerator[str, None]:
        """
        调用聊天模型
        如果 stream=True，返回 AsyncGenerator[str, None]
        """
        pass
