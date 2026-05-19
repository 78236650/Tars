"""Resolve InsightForge LLM provider — Chat endpoints first, providers.yaml fallback."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .llm_settings_store import InsightLlmSettings

logger = logging.getLogger(__name__)


_db = None


def init_llm_resolver(db) -> None:
    """Inject Database at startup so we don't import tars.main lazily."""
    global _db
    _db = db


@dataclass
class ResolvedInsightLlm:
    provider: Any
    selection: Dict[str, Any]
    source: str  # chat | tenant_settings | providers_yaml | none

    @property
    def label(self) -> str:
        return self.selection.get("label") or self.selection.get("model") or "未配置"


def get_chat_model_selection() -> Dict[str, Any]:
    """Current Chat/Agent model (models API switch state)."""
    try:
        from ..models.config import get_agent, get_current_model_selection

        base = get_current_model_selection()
        agent = get_agent()
        base["agent_model"] = getattr(agent, "current_model", base.get("model"))
        return base
    except Exception as e:
        logger.debug("get_chat_model_selection failed: %s", e)
        return {"provider": "ollama", "endpoint_id": None, "model": "", "label": ""}


def _label_for(provider: str, model: str, endpoint_name: Optional[str] = None) -> str:
    if provider == "openai_compatible" and endpoint_name:
        return f"{endpoint_name} / {model}"
    if provider == "ollama":
        return f"Ollama / {model}"
    return model or "未配置"


def _build_ollama_provider(model: str):
    from ..models import OllamaProvider

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return OllamaProvider(base_url=base_url, model=model or os.getenv("OLLAMA_MODEL", "llama3.2"))


def _build_endpoint_provider(endpoint_id: str, model: str):
    from ..database import EndpointStore
    from ..models import OpenAICompatProvider

    if _db is None:
        raise RuntimeError("llm_resolver not initialized; call init_llm_resolver(db) at startup")
    store = EndpointStore(_db)
    ep = store.get_by_id(endpoint_id)
    if not ep:
        raise ValueError(f"端点不存在: {endpoint_id}")
    if not ep.enabled:
        raise ValueError(f"端点已禁用: {ep.name}")
    if not model:
        model = (ep.models or [None])[0] or "gpt-3.5-turbo"
    return OpenAICompatProvider(
        base_url=ep.base_url,
        model=model,
        api_key=ep.api_key,
    ), ep.name


def build_provider_from_selection(
    selection: Dict[str, Any],
) -> Tuple[Any, Dict[str, Any]]:
    provider_type = selection.get("provider") or "ollama"
    model = selection.get("model") or ""
    endpoint_id = selection.get("endpoint_id")

    if provider_type == "openai_compatible" and endpoint_id:
        prov, ep_name = _build_endpoint_provider(endpoint_id, model)
        sel = {
            "provider": provider_type,
            "endpoint_id": endpoint_id,
            "model": model or getattr(prov, "model", ""),
            "endpoint_name": ep_name,
            "label": _label_for(provider_type, model or getattr(prov, "model", ""), ep_name),
        }
        return prov, sel

    if provider_type == "ollama":
        prov = _build_ollama_provider(model)
        m = getattr(prov, "model", model)
        sel = {
            "provider": "ollama",
            "endpoint_id": None,
            "model": m,
            "label": _label_for("ollama", m),
        }
        return prov, sel

    raise ValueError(f"不支持的 provider: {provider_type}")


def resolve_insight_llm(
    settings: InsightLlmSettings,
    override: Optional[Dict[str, Any]] = None,
) -> ResolvedInsightLlm:
    """
    Priority:
    1. override from profile request body
    2. tenant insight_llm_settings (use_chat_default → chat selection)
    3. providers.yaml default
    """
    if override:
        settings = InsightLlmSettings.from_dict(settings.tenant_id, override)

    if settings.use_chat_default:
        chat_sel = get_chat_model_selection()
        if chat_sel.get("model"):
            try:
                prov, sel = build_provider_from_selection(chat_sel)
                sel["use_chat_default"] = True
                return ResolvedInsightLlm(prov, sel, "chat")
            except Exception as e:
                logger.warning("[InsightForge] chat LLM unavailable: %s", e)

    if not settings.use_chat_default and settings.model:
        try:
            prov, sel = build_provider_from_selection(settings.to_dict())
            sel["use_chat_default"] = False
            return ResolvedInsightLlm(prov, sel, "tenant_settings")
        except Exception as e:
            logger.warning("[InsightForge] tenant LLM settings failed: %s", e)

    from .llm_synthesizer import get_default_llm_provider

    prov = get_default_llm_provider()
    if prov is not None:
        m = getattr(prov, "model", "") or os.getenv("OLLAMA_MODEL", "llama3.2")
        sel = {
            "provider": "ollama",
            "endpoint_id": None,
            "model": m,
            "label": _label_for("ollama", m) + " (providers.yaml)",
            "use_chat_default": False,
        }
        return ResolvedInsightLlm(prov, sel, "providers_yaml")

    return ResolvedInsightLlm(
        None,
        {"label": "未配置", "use_chat_default": settings.use_chat_default},
        "none",
    )
