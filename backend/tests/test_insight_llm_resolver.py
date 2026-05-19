"""InsightForge LLM resolver tests."""
from unittest.mock import MagicMock, patch

import pytest

from tars.insight.llm_resolver import build_provider_from_selection, resolve_insight_llm
from tars.insight.llm_settings_store import InsightLlmSettings


def test_resolve_uses_chat_when_use_chat_default():
    settings = InsightLlmSettings(tenant_id="t1", use_chat_default=True)
    mock_prov = MagicMock()
    chat_sel = {
        "provider": "openai_compatible",
        "endpoint_id": "ep-1",
        "model": "qwen-test",
        "label": "Qwen / qwen-test",
    }
    with patch("tars.insight.llm_resolver.get_chat_model_selection", return_value=chat_sel):
        with patch(
            "tars.insight.llm_resolver.build_provider_from_selection",
            return_value=(mock_prov, chat_sel),
        ):
            resolved = resolve_insight_llm(settings)
    assert resolved.source == "chat"
    assert resolved.provider is mock_prov


def test_build_ollama_provider():
    prov, sel = build_provider_from_selection(
        {"provider": "ollama", "model": "llama3.2", "endpoint_id": None}
    )
    assert sel["provider"] == "ollama"
    assert getattr(prov, "model", None) == "llama3.2"
