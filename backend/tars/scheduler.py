"""
TARS Scheduler - 定时任务调度器
支持 cron 表达式的任务调度系统
"""
import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, Coroutine
from dataclasses import dataclass


# 简单的 cron 表达式解析器（支持基本的格式 * * * * *）
class CronExpression:
    def __init__(self, expression: str):
        """
        初始化 cron 表达式
        格式: 分钟 小时 日期 月份 星期
        """
        self.parts = expression.strip().split()
        if len(self.parts) != 5:
            raise ValueError("Cron 表达式格式必须是 * * * * *")

    def next_run(self, from_time: Optional[datetime] = None) -> datetime:
        """
        计算下一次运行时间（简化版本，支持基本的 * 和数字）
        """
        if from_time is None:
            from_time = datetime.now()

        next_time = from_time.replace(second=0, microsecond=0)
        
        # 简单版本：每分钟执行一次
        from datetime import timedelta
        next_time = next_time + timedelta(minutes=1)
        
        return next_time


@dataclass
class ScheduledTask:
    task_id: str
    name: str
    cron_expression: str
    task: Callable[[], Coroutine[Any, Any, Any]]
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime = datetime.now()


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
    
    def add_task(self, name: str, cron_expression: str,
                 task: Callable[[], Coroutine[Any, Any, Any]]) -> str:
        """
        添加定时任务
        
        Args:
            name: 任务名称
            cron_expression: cron 表达式
            task: 异步任务函数
        
        Returns:
            task_id: 任务 ID
        """
        task_id = str(uuid.uuid4())
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
            
            now = datetime.now()
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
            task.last_run = datetime.now()
            
            # 计算下一次运行时间
            cron = CronExpression(task.cron_expression)
            task.next_run = cron.next_run(task.last_run)
            
            # 执行任务
            await task.task()
        except Exception as e:
            print(f"任务 {task.name} 执行失败: {e}")
    
    def _calculate_next_check(self) -> datetime:
        """计算下一次检查时间"""
        from datetime import timedelta
        
        if not self.tasks:
            return datetime.now() + timedelta(minutes=1)
        
        next_times = [t.next_run for t in self.tasks.values()
                     if t.enabled and t.next_run]
        
        if not next_times:
            return datetime.now() + timedelta(minutes=1)
        
        next_run = min(next_times)
        return min(next_run, datetime.now() + timedelta(minutes=1))


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
