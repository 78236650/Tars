"""Memory compression scheduler hooks."""


class MemoryScheduler:
    def __init__(self, compressor, scheduler):
        self.compressor = compressor
        self.scheduler = scheduler
        self.task_id = None

    def ensure_started(self):
        if self.scheduler is None or self.task_id:
            return

        async def _run():
            await self.compressor.compress_all()

        self.task_id = self.scheduler.add_task(
            name="memory-daily-compress",
            cron_expression="0 3 * * *",
            task=_run,
            task_id="memory-daily-compress",
        )
