"""任务执行器 v2.4 — 集成 StepVerifier + ActPolicy + ArtifactsCollector"""
import asyncio
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from .models import TaskPlan, TaskStep, StepStatus
from .verifier import StepVerifier, verifier as default_verifier
from .act_policy import ActPolicy, ActDecision
from .artifacts_collector import ArtifactsCollector
from ..tools.registry import ToolRegistry
from ..tools.base import ToolResult


def now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


class TaskExecutor:
    """v2.4 执行器：Check → Act + artifacts 追踪"""

    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
        self.verifier = default_verifier
        self.act_policy = ActPolicy()
        self._pending_decisions: Dict[str, asyncio.Future] = {}

    async def execute(self, plan: TaskPlan, session_id: str, channel,
                      workspace_path: str = ".") -> Dict[int, ToolResult]:
        """执行计划，返回每步的结果。

        流程：Do → Check → {pass → next / fail → Act(retry×3 → ask → abort/skip)}
        """
        results: Dict[int, ToolResult] = {}
        collector = ArtifactsCollector(workspace_path)
        collector.take_snapshot()

        await channel.send(session_id, {
            "type": "plan_created",
            "session_id": session_id,
            "plan": plan.to_dict(),
            "timestamp": now_iso(),
        })

        for step in plan.steps:
            step_dict = step.to_dict()
            resolved_args = self._resolve_placeholders(step.arguments, results)

            # 执行（带 Check + Act）
            step_result = await self._execute_step_with_act(
                step, step_dict, resolved_args, session_id, channel, workspace_path
            )
            results[step.id] = step_result

            if step_result.success:
                step.status = StepStatus.COMPLETED
                step.output = step_result.output
            else:
                step.status = StepStatus.FAILED
                step.error = step_result.error

            await channel.send(session_id, {
                "type": "plan_step_complete",
                "session_id": session_id,
                "step_id": step.id,
                "success": step_result.success,
                "output": (step_result.output or "")[:500],
                "error": step_result.error,
                "timestamp": now_iso(),
            })

            # 失败后用户决策
            if not step_result.success:
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

        # 采集 artifacts
        artifacts = collector.collect_new_files()
        for step in plan.steps:
            artifacts.extend(ArtifactsCollector.collect_from_step(step.to_dict()))
        artifacts = list(set(artifacts))

        await channel.send(session_id, {
            "type": "plan_complete",
            "session_id": session_id,
            "status": "completed",
            "steps": [s.to_dict() for s in plan.steps],
            "artifacts": artifacts,
            "timestamp": now_iso(),
        })
        return results

    async def _execute_step_with_act(self, step: TaskStep, step_dict: dict,
                                       args: Dict, session_id: str, channel,
                                       workspace_path: str) -> ToolResult:
        """单步执行完整流程：Do → Check → Act"""
        tool = self.tool_registry.get(step.tool)
        if not tool:
            return ToolResult(success=False, output="", error=f"工具 '{step.tool}' 不存在")

        await channel.send(session_id, {
            "type": "plan_step_start",
            "session_id": session_id,
            "step_id": step.id,
            "description": step.description,
            "tool": step.tool,
            "timestamp": now_iso(),
        })

        step.status = StepStatus.RUNNING
        retries_done = 0
        last_result = None

        while True:
            # Do
            try:
                last_result = await tool.execute(**args)
            except Exception as e:
                last_result = ToolResult(success=False, output="", error=str(e))

            # Check
            verify_result = self.verifier.check(step_dict, last_result, workspace_path)

            if verify_result.passed:
                step.status = StepStatus.COMPLETED
                step.output = last_result.output
                return last_result

            # Act: verify failed → retry or ask user
            step.retries = retries_done
            step.error = verify_result.message
            step.status = StepStatus.FAILED

            if self.act_policy.should_retry(retries_done):
                retries_done += 1
                wait = self.act_policy.backoff_seconds(retries_done)
                await channel.send(session_id, {
                    "type": "step_retrying",
                    "session_id": session_id,
                    "step_id": step.id,
                    "attempt": retries_done,
                    "error": verify_result.message,
                    "timestamp": now_iso(),
                })
                await asyncio.sleep(wait)
                continue

            # 超出自动重试 → 询问用户
            decision = await self.act_policy.ask_user(step_dict, session_id, channel)
            if decision == ActDecision.RETRY:
                retries_done += 1
                continue
            if decision == ActDecision.SKIP:
                step.status = StepStatus.SKIPPED
                return ToolResult(success=True, output="用户跳过此步骤")
            # ABORT
            return ToolResult(success=False, output="", error=f"用户中止: {verify_result.message}")

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
