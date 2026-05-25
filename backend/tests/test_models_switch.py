"""Model switch — Ollama vs openai_compatible provider instance."""
from unittest.mock import MagicMock, patch

import pytest

from tars.models import OpenAICompatProvider, OllamaProvider
from tars.models.config import _switch_agent_to_ollama


def test_switch_agent_to_ollama_replaces_remote_provider():
    agent = MagicMock()
    agent.provider = OpenAICompatProvider(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
        api_key="sk-test",
    )
    agent.current_model = "qwen-plus"

    with patch("tars.models.config._sync_llm_chain") as sync:
        _switch_agent_to_ollama(agent, "qwen3:8b")

    assert isinstance(agent.provider, OllamaProvider)
    assert agent.provider.model == "qwen3:8b"
    assert agent.current_model == "qwen3:8b"
    sync.assert_called_once_with(agent)


def test_agent_switch_model_from_remote_to_ollama():
    from tars.agent.agent import AgentV2

    agent = AgentV2(provider=OpenAICompatProvider(
        base_url="https://example.com/v1",
        model="remote-model",
        api_key="k",
    ))
    agent.current_model = "remote-model"

    ok = agent.switch_model("gemma4:e2b")
    assert ok is True
    assert isinstance(agent.provider, OllamaProvider)
    assert agent.provider.model == "gemma4:e2b"
    assert agent.current_model == "gemma4:e2b"
