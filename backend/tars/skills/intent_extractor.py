"""Lightweight intent extraction for SkillRouter v4.3.2."""
from dataclasses import dataclass, field
from typing import List, Optional

from .signal_extractor import extract_signals


@dataclass
class Intent:
    text: str
    keywords: List[str] = field(default_factory=list)
    intent_label: str = "general.chat"
    embedding: Optional[List[float]] = None


class IntentExtractor:
    """Extract routing intent: keywords + optional embedding vector."""

    def __init__(self, embedding_provider=None, use_embedding: bool = True):
        self.embedding_provider = embedding_provider
        self.use_embedding = use_embedding and embedding_provider is not None

    def extract(self, message: str) -> Intent:
        if not message:
            return Intent(text="", keywords=[], intent_label="general.chat")

        intent_label, entities, keywords = extract_signals(message)
        merged_keywords = list({*keywords, *entities})

        embedding = None
        if self.use_embedding:
            try:
                vectors = self.embedding_provider.encode([message])
                if vectors:
                    embedding = vectors[0]
            except Exception:
                embedding = None

        return Intent(
            text=message,
            keywords=merged_keywords,
            intent_label=intent_label,
            embedding=embedding,
        )
