"""Cron task executor registry base types."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..runtime import CronRuntime


class CronExecutionContext:
    def __init__(self, runtime: "CronRuntime"):
        self.runtime = runtime
        self.db = runtime.db
        self.connection_manager = runtime.connection_manager
        self.outbound = runtime.outbound
        self.agent = runtime.agent
        self.audit_extras: dict[str, Any] = {}


class CronTaskExecutor(ABC):
    task_type: str

    @abstractmethod
    async def execute(self, ctx: CronExecutionContext, job: Any, config: dict[str, Any]) -> None:
        pass
