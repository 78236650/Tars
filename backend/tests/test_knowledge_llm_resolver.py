"""Knowledge enrichment LLM resolver tests."""
from unittest.mock import MagicMock, patch

from tars.insight.llm_resolver import resolve_knowledge_llm


def test_resolve_knowledge_llm_uses_chat_selection():
    mock_prov = MagicMock()
    chat_sel = {
        "provider": "openai_compatible",
        "endpoint_id": "ep-1",
        "model": "qwen-plus",
        "label": "DashScope / qwen-plus",
    }
    with patch("tars.insight.llm_resolver.get_chat_model_selection", return_value=chat_sel):
        with patch(
            "tars.insight.llm_resolver.build_provider_from_selection",
            return_value=(mock_prov, chat_sel),
        ):
            resolved = resolve_knowledge_llm("default", llm_settings_store=MagicMock())
    assert resolved.source == "chat"
    assert resolved.provider is mock_prov
    assert resolved.selection["model"] == "qwen-plus"


def test_resolve_knowledge_llm_falls_back_to_agent_provider():
    from tars.models import OllamaProvider

    mock_prov = OllamaProvider(model="gpt-4o")
    mock_agent = MagicMock(provider=mock_prov, current_model="gpt-4o")
    with patch("tars.insight.llm_resolver.get_chat_model_selection", return_value={"model": "", "provider": "ollama"}):
        with patch("tars.models.config.get_agent", return_value=mock_agent):
            resolved = resolve_knowledge_llm("default")
    assert resolved.source == "chat_agent"
    assert resolved.provider is mock_prov


def test_enricher_resolve_provider_without_settings_store():
    from tars.knowledge.enricher import _resolve_provider

    mock_prov = MagicMock()
    chat_sel = {"provider": "ollama", "model": "llama3.2", "endpoint_id": None, "label": "Ollama / llama3.2"}
    with patch("tars.insight.llm_resolver.resolve_knowledge_llm") as mock_resolve:
        mock_resolve.return_value = MagicMock(
            provider=mock_prov,
            selection=chat_sel,
            source="chat",
        )
        prov, sel = _resolve_provider("default", llm_settings_store=None)
    assert prov is mock_prov
    assert sel["model"] == "llama3.2"
