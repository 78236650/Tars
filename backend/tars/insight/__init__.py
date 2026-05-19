"""TARS InsightForge 鉴数 — business data cold-start & metric Q&A."""
from .version import CAPABILITY_NAME, CAPABILITY_TAG, INS_VERSION, INS_API_VERSION
from .config import get_insight_config, load_insight_config

__all__ = [
    "CAPABILITY_NAME",
    "CAPABILITY_TAG",
    "INS_VERSION",
    "INS_API_VERSION",
    "get_insight_config",
    "load_insight_config",
]
