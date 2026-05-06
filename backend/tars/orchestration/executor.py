"""任务执行器 — 按计划执行步骤，支持重试、占位符替换、失败决策"""
import asyncio
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from .models import TaskPlan, TaskStep, StepStatus
from ..tools.registry import ToolRegistry
from ..tools.base import ToolResult


def now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


class TaskExecutor:
    """按计划执行步骤"""

    def __init__(self, tool_registry: ToolRegistry, max_retries: int = 2):
        self.tool_registry = tool_registry
        self.max_retries = max_retries
        self._pending_decisions: Dict[str, asyncio.Future] = {}

    async def execute(self, plan: TaskPlan, session_id: str, channel) -> Dict[int, ToolResult]:
        """执行计划，返回每步的结果"""
        results: Dict[int, ToolResult] = {}

        await channel.send(session_id, {
            "type": "plan_created",
            "session_id": session_id,
            "plan": plan.to_dict(),
            "timestamp": now_iso(),
        })

        for step in plan.steps:
            await channel.send(session_id, {
                "type": "plan_step_start",
                "session_id": session_id,
                "step_id": step.id,
                "description": step.description,
                "tool": step.tool,
                "timestamp": now_iso(),
            })

            step.status = StepStatus.RUNNING
            resolved_args = self._resolve_placeholders(step.arguments, results)

            result = await self._execute_with_retry(step, resolved_args, session_id, channel)
            results[step.id] = result

            if result.success:
                step.status = StepStatus.COMPLETED
                step.output = result.output
            else:
                step.status = StepStatus.FAILED
                step.error = result.error

            await channel.send(session_id, {
                "type": "plan_step_complete",
                "session_id": session_id,
                "step_id": step.id,
                "success": result.success,
                "output": result.output[:500] if result.output else "",
                "error": result.error,
                "timestamp": now_iso(),
            })

            # 失败决策
            if not result.success:
                decision = await self._ask_user_decision(step, session_id, channel)
                if decision == "abort":
                    await channel.send(session_id, {
                        "type": "plan_complete",
                        "session_id": session_id,
                        "status": "aborted",
                        "timestamp": now_iso(),
                    })
                    return results
                if decision == "skip":
                    step.status = StepStatus.SKIPPED
                    continue

        await channel.send(session_id, {
            "type": "plan_complete",
            "session_id": session_id,
            "status": "completed",
            "steps": [s.to_dict() for s in plan.steps],
            "timestamp": now_iso(),
        })
        return results

    async def _execute_with_retry(self, step: TaskStep, args: Dict, session_id: str, channel) -> ToolResult:
        """执行工具，失败自动重试"""
        tool = self.tool_registry.get(step.tool)
        if not tool:
            return ToolResult(success=False, output="", error=f"工具 '{step.tool}' 不存在")

        last_result = None
        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                step.retries = attempt
                await channel.send(session_id, {
                    "type": "plan_step_retry",
                    "session_id": session_id,
                    "step_id": step.id,
                    "attempt": attempt,
                    "timestamp": now_iso(),
                })
                await asyncio.sleep(1)

            try:
                last_result = await tool.execute(**args)
                if last_result.success:
                    return last_result
            except Exception as e:
                last_result = ToolResult(success=False, output="", error=str(e))

        return last_result or ToolResult(success=False, output="", error="未知错误")

    async def _ask_user_decision(self, step: TaskStep, session_id: str, channel) -> str:
        """发 plan_step_failed 等用户决策。超时默认 abort。"""
        decision_key = f"{session_id}_{step.id}"
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_decisions[decision_key] = fut

        await channel.send(session_id, {
            "type": "plan_step_failed",
            "session_id": session_id,
            "step_id": step.id,
            "description": step.description,
            "error": step.error,
            "timestamp": now_iso(),
        })

        try:
            decision = await asyncio.wait_for(fut, timeout=120)
            return decision
        except asyncio.TimeoutError:
            return "abort"
        finally:
            self._pending_decisions.pop(decision_key, None)

    def submit_decision(self, session_id: str, step_id: int, decision: str):
        """前端决策回传"""
        decision_key = f"{session_id}_{step_id}"
        fut = self._pending_decisions.get(decision_key)
        if fut and not fut.done():
            fut.set_result(decision)

    def _resolve_placeholders(self, args: Any, results: Dict[int, ToolResult]) -> Any:
        """递归替换 {{step_N.output}} 占位符"""
        if isinstance(args, str):
            def replace(match):
                step_id = int(match.group(1))
                field = match.group(2)
                result = results.get(step_id)
                if not result:
                    return match.group(0)
                if field == "output":
                    return result.output or ""
                if field == "error":
                    return result.error or ""
                return match.group(0)
            return re.sub(r'\{\{step_(\d+)\.(\w+)\}\}', replace, args)
        if isinstance(args, dict):
            return {k: self._resolve_placeholders(v, results) for k, v in args.items()}
        if isinstance(args, list):
            return [self._resolve_placeholders(v, results) for v in args]
        return args
