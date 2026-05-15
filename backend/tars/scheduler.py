"""
TARS Scheduler - 定时任务调度器
支持 cron 表达式的任务调度系统
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Callable, Coroutine, Set
from dataclasses import dataclass, field


class CronExpression:
    def __init__(self, expression: str):
        """初始化 cron 表达式，格式: 分钟 小时 日期 月份 星期"""
        self.parts = expression.strip().split()
        if len(self.parts) != 5:
            raise ValueError("Cron 表达式格式必须是 * * * * *")
        self._minute = self._parse_part(self.parts[0], 0, 59)
        self._hour = self._parse_part(self.parts[1], 0, 23)
        self._day = self._parse_part(self.parts[2], 1, 31)
        self._month = self._parse_part(self.parts[3], 1, 12)
        self._weekday = self._parse_part(self.parts[4], 0, 7)

    def next_run(self, from_time: Optional[datetime] = None) -> datetime:
        """计算下一次运行时间，支持 `*`、数字、范围、步长、逗号列表。"""
        if from_time is None:
            from_time = _local_now()

        candidate = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
        max_lookahead = 366 * 24 * 60
        for _ in range(max_lookahead):
            if self._matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)
        raise ValueError(f"Cron 表达式在一年内未找到可执行时间: {self.expression}")

    @property
    def expression(self) -> str:
        return " ".join(self.parts)

    def _matches(self, dt: datetime) -> bool:
        cron_weekday = (dt.weekday() + 1) % 7
        return (
            dt.minute in self._minute
            and dt.hour in self._hour
            and dt.day in self._day
            and dt.month in self._month
            and cron_weekday in self._weekday
        )

    def _parse_part(self, token: str, minimum: int, maximum: int) -> Set[int]:
        values: Set[int] = set()
        for part in token.split(","):
            part = part.strip()
            if not part:
                continue
            if part == "*":
                values.update(range(minimum, maximum + 1))
                continue

            base, step = (part.split("/", 1) + ["1"])[:2] if "/" in part else (part, "1")
            step_value = int(step)
            if step_value <= 0:
                raise ValueError("Cron 步长必须大于 0")

            if base == "*":
                start, end = minimum, maximum
            elif "-" in base:
                start_str, end_str = base.split("-", 1)
                start, end = int(start_str), int(end_str)
            else:
                start = end = int(base)

            if start < minimum or end > maximum or start > end:
                raise ValueError(f"Cron 字段超出范围: {token}")
            values.update(range(start, end + 1, step_value))

        if not values:
            raise ValueError(f"无效的 Cron 字段: {token}")
        return values


def _local_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


@dataclass
class ScheduledTask:
    task_id: str
    name: str
    cron_expression: str
    task: Callable[[], Coroutine[Any, Any, Any]]
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime = field(default_factory=_local_now)


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}
        self.running = False
        self._task = None
        self._event = asyncio.Event()
    
    def start(self):
        """启动调度器"""
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._run_scheduler())
    
    async def stop(self):
        """停止调度器"""
        if not self.running:
            return
        self.running = False
        self._event.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, 5.0)
            except:
                pass
    
    def add_task(
        self,
        name: str,
        cron_expression: str,
        task: Callable[[], Coroutine[Any, Any, Any]],
        task_id: Optional[str] = None,
    ) -> str:
        """
        添加定时任务
        
        Args:
            name: 任务名称
            cron_expression: cron 表达式
            task: 异步任务函数
        
        Returns:
            task_id: 任务 ID
        """
        task_id = task_id or str(uuid.uuid4())
        cron = CronExpression(cron_expression)
        next_run = cron.next_run()

        scheduled_task = ScheduledTask(
            task_id=task_id,
            name=name,
            cron_expression=cron_expression,
            task=task,
            next_run=next_run
        )
        
        self.tasks[task_id] = scheduled_task
        self._event.set()
        return task_id
    
    def remove_task(self, task_id: str):
        """移除任务"""
        if task_id in self.tasks:
            del self.tasks[task_id]
    
    def get_tasks(self) -> List[ScheduledTask]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def enable_task(self, task_id: str, enabled: bool = True):
        """启用或禁用任务"""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = enabled
    
    async def _run_scheduler(self):
        """调度器主循环"""
        while self.running:
            self._event.clear()
            
            now = _local_now()
            tasks_to_run = []
            
            # 检查所有任务
            for task_id, task in list(self.tasks.items()):
                if not task.enabled:
                    continue
                
                if task.next_run and now >= task.next_run:
                    tasks_to_run.append(task)
            
            # 执行到期任务
            for task in tasks_to_run:
                asyncio.create_task(self._run_task(task))
            
            # 计算下一次检查时间
            next_check = self._calculate_next_check()
            wait_time = (next_check - now).total_seconds()
            if wait_time > 0:
                try:
                    await asyncio.wait_for(self._event.wait(), wait_time)
                except asyncio.TimeoutError:
                    pass
    
    async def _run_task(self, task: ScheduledTask):
        """执行单个任务"""
        try:
            task.last_run = _local_now()
            
            # 计算下一次运行时间
            cron = CronExpression(task.cron_expression)
            task.next_run = cron.next_run(task.last_run)
            
            # 执行任务
            await task.task()
        except Exception as e:
            print(f"任务 {task.name} 执行失败: {e}")
    
    def _calculate_next_check(self) -> datetime:
        """计算下一次检查时间"""
        if not self.tasks:
            return _local_now() + timedelta(minutes=1)

        next_times = [t.next_run for t in self.tasks.values()
                     if t.enabled and t.next_run]

        if not next_times:
            return _local_now() + timedelta(minutes=1)

        next_run = min(next_times)
        return min(next_run, _local_now() + timedelta(minutes=1))


# ============ 全局调度器实例 ============
_scheduler = TaskScheduler()


def get_scheduler() -> TaskScheduler:
    """获取全局调度器实例"""
    return _scheduler


async def init_scheduler():
    """初始化调度器"""
    get_scheduler().start()
    print("定时任务调度器已启动")


async def shutdown_scheduler():
    """关闭调度器"""
    await get_scheduler().stop()
    print("定时任务调度器已停止")
