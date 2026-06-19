"""Semantic layer domain models."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GlossaryTerm:
    id: str
    term: str
    definition: str
    domain: str = "port"
    aliases: list[str] = field(default_factory=list)
    user_id: str = "default"


@dataclass
class FieldSemantic:
    id: str
    datasource_id: str
    table_name: str
    column_name: str
    term_id: str | None = None
    suggested_term: str | None = None
    confidence: float = 0.0
    status: str = "suggested"  # suggested | confirmed | rejected
    user_id: str = "default"
