"""Memory compression & KB promotion scheduler hooks."""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ..config.memory import config

if TYPE_CHECKING:
    from .manager import MemoryManager


class MemoryScheduler:
    def __init__(self, memory_manager: "MemoryManager", scheduler):
        self.memory_manager = memory_manager
        self.compressor = memory_manager.compressor
        self.scheduler = scheduler
        self.compress_task_id: Optional[str] = None
        self.promote_task_id: Optional[str] = None

    def ensure_started(self):
        if self.scheduler is None:
            return

        if config.compressor_enabled and not self.compress_task_id:
            async def _compress():
                await self.compressor.compress_all()

            self.compress_task_id = self.scheduler.add_task(
                name="memory-daily-compress",
                cron_expression="0 3 * * *",
                task=_compress,
                task_id="memory-daily-compress",
            )

        if config.kb_promotion_enabled and not self.promote_task_id:
            async def _promote_kb():
                from .kb_promotion import run_scheduled_kb_promotion

                report = await run_scheduled_kb_promotion(self.memory_manager)
                print(f"[MemoryScheduler] KB promotion: {report}")

            self.promote_task_id = self.scheduler.add_task(
                name="memory-kb-promote",
                cron_expression="0 4 * * *",
                task=_promote_kb,
                task_id="memory-kb-promote",
            )
