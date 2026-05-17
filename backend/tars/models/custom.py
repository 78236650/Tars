"""TARS Custom Provider — backward-compat redirect to plugins/openai_compat.py."""
from .plugins.openai_compat import OpenAICompatProvider, _normalize_openai_response

CustomProvider = OpenAICompatProvider

__all__ = ["CustomProvider", "OpenAICompatProvider", "_normalize_openai_response"]
