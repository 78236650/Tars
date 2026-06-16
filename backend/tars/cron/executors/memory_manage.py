"""Cron Executor for Memory Sleep Agent"""
import json
from typing import Any

from .base import CronTaskExecutor, CronExecutionContext
from ...memory.sleep_agent import MemorySleepAgent

class MemoryManageExecutor(CronTaskExecutor):
    """
    定期执行的记忆整理器 (Sleep-time Agent)。
    负责在系统空闲时对用户的长期记忆进行去重、合并与衰减处理。
    """
    
    task_type = "memory_manage"
    
    async def execute(self, ctx: CronExecutionContext, job: Any, config: dict[str, Any]) -> None:
        tenant_id = getattr(job, "tenant_id", "default")
        user_id = getattr(job, "user_id", "default")
        
        # 初始化 Sleep Agent (v5.2.0: 传入 db 以支持真实整理逻辑)
        db = getattr(ctx.runtime, "db", None) if ctx.runtime else None
        agent = MemorySleepAgent(db=db)
        
        # 执行整理任务
        stats = await agent.run_consolidation(tenant_id, user_id)
        
        # 记录审计额外信息
        ctx.audit_extras = {"stats": stats}
        
        # 可选：如果整理结果需要通知用户，可以通过 ctx.runtime.deliver_event 发送
        # (通常在后台静默执行，不需要发送事件)
