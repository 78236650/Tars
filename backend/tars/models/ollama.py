"""TARS Ollama Provider — backward-compat redirect to plugins/ollama.py."""
from .plugins.ollama import OllamaProvider

__all__ = ["OllamaProvider"]
