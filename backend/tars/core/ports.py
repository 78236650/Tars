"""Port/Adapter contracts between Layer1 (Agent Core) and Layer2 (Data Platform)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from tars.database import Database
    from tars.tools.registry import ToolRegistry


@dataclass(frozen=True)
class DataSourceSummary:
    id: str
    name: str
    connection_type: str


@dataclass(frozen=True)
class MetricAnswer:
    value: Any
    definition: str
    sql: str | None = None


class DataPort(Protocol):
    """Layer2 data capabilities exposed to Layer1 tools."""

    async def list_datasources(self, tenant_id: str) -> list[DataSourceSummary]: ...

    def fetch_rows(
        self,
        datasource_id: str,
        *,
        table: str | None = None,
        sql: str | None = None,
        max_rows: int = 10_000,
        tenant_id: str = "org_default",
    ) -> Any: ...

    async def ask_metric(
        self, tenant_id: str, question: str, datasource_id: str
    ) -> MetricAnswer: ...


class ToolContributor(Protocol):
    """Layer2 module registers agent-callable tools through this interface."""

    module_name: str

    def register_tools(self, registry: ToolRegistry, ports: DataPort) -> None: ...

    def register_routes(self, app: FastAPI, db: Database) -> None: ...


@dataclass
class BootstrapDeps:
    """Shared dependencies passed to bootstrap layers."""

    app: Any
    db: Any
    agent: Any
    tool_registry: Any
    module_registry: Any
    evolution_manager: Any | None = None
