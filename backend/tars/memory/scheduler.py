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
        self.alert_task_id: Optional[str] = None

    def ensure_started(self):
        if self.scheduler is None:
            return

        # v5.0.5/A3: 定时调度用独立开关 compressor_scheduled
        if config.compressor_scheduled and not self.compress_task_id:
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

        # v5.0.5/A4: 主动预警巡检（每 6 小时）
        if not self.alert_task_id:
            async def _scan_alerts():
                try:
                    from ..evolution.alerting import AlertEngine
                    engine = AlertEngine(self.memory_manager.db)
                    alerts = engine.scan(self.memory_manager.tenant_id)
                    if alerts:
                        print(f"[AlertEngine] {len(alerts)} 条预警:")
                        for a in alerts:
                            print(f"  [{a.severity}] {a.title}: {a.description}")
                except Exception as exc:
                    print(f"[AlertEngine] 巡检失败: {exc}")

            self.alert_task_id = self.scheduler.add_task(
                name="memory-alert-scan",
                cron_expression="0 */6 * * *",
                task=_scan_alerts,
                task_id="memory-alert-scan",
            )
