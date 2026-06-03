# TARS Model Layer - Base Provider (v4.0.0)
# Layer 4: 模型层抽象 — plugin architecture
from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator, Optional
from dataclasses import dataclass, field


# ── Phase 3 dataclasses ────────────────────────────────────────────

@dataclass
class ModelInfo:
    id: str
    name: str = ""
    supports_tools: bool = False
    supports_vision: bool = False
    context_length: int = 4096


@dataclass
class ChatResponse:
    content: str
    model: str = ""
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: Optional[Dict[str, int]] = None


# ── Legacy dataclasses (kept for backward compat) ──────────────────

@dataclass
class ChatMessage:
    role: str  # user, assistant, system, tool
    content: str
    tool_call_id: str | None = None
    tool_calls: List[Dict[str, Any]] | None = None
    name: str | None = None
    images: List[str] | None = None
    reasoning_content: str | None = None  # DeepSeek 推理模型的推理过程内容


@dataclass
class ModelResponse:
    content: str
    model: str
    usage: Dict[str, Any] | None = None


# ── Abstract base ──────────────────────────────────────────────────

class ProviderBase(ABC):
    """Abstract base for all LLM providers (v4.0.0).

    Minimum contract: must implement chat() and list_models().
    Optional: supports_tools / supports_vision / test_connection().
    """

    name: str = ""
    display_name: str = ""
    auth_type: str = "none"  # none | api_key | bearer
    supports_tools: bool = False
    supports_vision: bool = False

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
    ):
        """Send chat request. Returns ChatResponse or AsyncGenerator[str, None]."""
        ...

    @abstractmethod
    async def list_models(self) -> List[str]:
        """Return available model IDs."""
        ...

    async def test_connection(self) -> tuple[bool, str]:
        """Quick connectivity check. Override for provider-specific logic."""
        return False, "not implemented"


# ── Backward compatibility alias ───────────────────────────────────

# LLMProvider is the old name — kept so existing imports don't break.
LLMProvider = ProviderBase
