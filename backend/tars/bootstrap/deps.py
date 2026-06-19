"""Bootstrap dependency container."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BootstrapDeps:
    app: Any
    db: Any
    agent: Any
    tool_registry: Any
    module_registry: Any
    evolution_manager: Any | None = None
    meeting_tool: Any | None = None
    vector_store: Any | None = None
    embedding_provider: Any | None = None
