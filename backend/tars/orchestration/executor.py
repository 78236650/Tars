"""任务执行器 v2.4 — 集成 StepVerifier + ActPolicy + ArtifactsCollector + 危险命令拦截"""
import asyncio
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from .models import TaskPlan, TaskStep, StepStatus, PlanStatus, PlanCheckpoint
from .verifier import StepVerifier, verifier as default_verifier
from .act_policy import ActPolicy, ActDecision
from .artifacts_collector import ArtifactsCollector
from ..tools.registry import ToolRegistry
from ..tools.base import ToolResult


def now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


DANGEROUS_COMMANDS = [
    "rm -rf", "mkfs", "dd if=", "> /dev/sd", "chmod -R 777 /", "kill -9 1",
]


class TaskExecutor:
    """v2.4 执行器：Check → Act + artifacts 追踪"""

    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
        self.verifier = default_verifier
        self.act_policy = ActPolicy()
        self._pending_decisions: Dict[str, asyncio.Future] = {}

    async def execute(
        self,
        plan: TaskPlan,
        session_id: str,
        channel,
        workspace_path: str = ".",
        plan_id: Optional[str] = None,
        plan_store=None,
        start_from_step_id: int = 1,
        skill_id: Optional[str] = None,
        skill_registry=None,
        verification_gate=None,
        audit_store=None,
    ) -> Dict[int, ToolResult]:
        """执行计划，返回每步的结果。

        流程：Do → Check → {pass → next / fail → Act(retry×3 → ask → abort/skip)}
        """
        results: Dict[int, ToolResult] = {}
        collector = ArtifactsCollector(workspace_path)
        collector.take_snapshot()
        effective_plan_id = plan_id or plan.id

        await channel.send(session_id, {
            "type": "plan_created",
            "session_id": session_id,
            "plan_id": effective_plan_id,
            "plan": plan.to_dict(),
            "timestamp": now_iso(),
        })

        for step in plan.steps:
            if step.id < start_from_step_id:
                continue

            if plan_store and effective_plan_id:
                stored = plan_store.get(effective_plan_id)
                if stored and stored.status in (PlanStatus.CANCELLED, PlanStatus.REJECTED):
                    await channel.send(session_id, {
                        "type": "plan_complete",
                        "session_id": session_id,
                        "plan_id": effective_plan_id,
                        "status": stored.status.value,
                        "timestamp": now_iso(),
                    })
                    return results

            step_dict = step.to_dict()
            resolved_args = self._resolve_placeholders(step.arguments, results)

            step_result = await self._execute_step_with_act(
                step, step_dict, resolved_args, session_id, channel, workspace_path
            )
            results[step.id] = step_result

            if step_result.success:
                step.status = StepStatus.COMPLETED
                step.output = step_result.output
                cp_status = "done"
            else:
                step.status = StepStatus.FAILED
                step.error = step_result.error
                cp_status = "failed"

            if plan_store and effective_plan_id:
                plan_store.add_checkpoint(PlanCheckpoint(
                    plan_id=effective_plan_id,
                    step_id=step.id,
                    status=cp_status,
                    output=(step.output or step.error or "")[:500],
                    timestamp=now_iso(),
                    retry_count=step.retries,
                ))

            await channel.send(session_id, {
                "type": "plan_step_complete",
                "session_id": session_id,
                "plan_id": effective_plan_id,
                "step_id": step.id,
                "success": step_result.success,
                "output": (step_result.output or "")[:500],
                "error": step_result.error,
                "timestamp": now_iso(),
            })

            if not step_result.success:
                if plan_store and effective_plan_id:
                    plan_store.update_status(effective_plan_id, PlanStatus.FAILED)
                decision = await self._ask_user_decision(step, session_id, channel)
                if decision == "abort":
                    await channel.send(session_id, {
                        "type": "plan_complete",
                        "session_id": session_id,
                        "plan_id": effective_plan_id,
                        "status": "aborted",
                        "timestamp": now_iso(),
                    })
                    return results
                if decision == "skip":
                    step.status = StepStatus.SKIPPED
                    if plan_store and effective_plan_id:
                        plan_store.add_checkpoint(PlanCheckpoint(
                            plan_id=effective_plan_id,
                            step_id=step.id,
                            status="skipped",
                            output=step.error,
                            timestamp=now_iso(),
                            retry_count=step.retries,
                        ))
                    continue

        artifacts = collector.collect_new_files()
        for step in plan.steps:
            artifacts.extend(ArtifactsCollector.collect_from_step(step.to_dict()))
        artifacts = list(set(artifacts))

        step_failed = any(
            s.status == StepStatus.FAILED for s in plan.steps if s.id >= start_from_step_id
        )
        final_status = "failed" if step_failed else "completed"

        if not step_failed and skill_id and skill_registry:
            skill = skill_registry.get(skill_id)
            verify_steps = getattr(skill, "verify", None) if skill else None
            if verify_steps:
                from .verification import get_verification_gate
                gate = verification_gate or get_verification_gate()
                verify_result = await gate.run(
                    verify_steps,
                    mode=getattr(skill, "verify_mode", "strict"),
                    cwd=workspace_path,
                )
                if audit_store and effective_plan_id:
                    audit_store.record(effective_plan_id, skill_id, verify_result)
                await channel.send(session_id, {
                    "type": "verification_complete" if verify_result.passed else "verification_failed",
                    "session_id": session_id,
                    "plan_id": effective_plan_id,
                    "skill_id": skill_id,
                    "passed": verify_result.passed,
                    "status": verify_result.status,
                    "step_results": [
                        {
                            "command": s.command,
                            "expect": s.expect,
                            "passed": s.passed,
                            "message": s.message,
                        }
                        for s in verify_result.step_results
                    ],
                    "timestamp": now_iso(),
                })
                if not verify_result.passed:
                    final_status = "failed"
                elif verify_result.status == "done_with_warnings":
                    final_status = "completed_with_warnings"

        if plan_store and effective_plan_id:
            if final_status in ("failed",):
                plan_store.update_status(effective_plan_id, PlanStatus.FAILED)
            else:
                plan_store.update_status(effective_plan_id, PlanStatus.DONE)

        await channel.send(session_id, {
            "type": "plan_complete",
            "session_id": session_id,
            "plan_id": effective_plan_id,
            "status": final_status,
            "steps": [s.to_dict() for s in plan.steps],
            "artifacts": artifacts,
            "timestamp": now_iso(),
        })
        return results

    async def resume(
        self,
        plan_id: str,
        session_id: str,
        channel,
        workspace_path: str = ".",
        plan_store=None,
        skill_registry=None,
        audit_store=None,
        verification_gate=None,
    ) -> Dict[int, ToolResult]:
        if not plan_store:
            raise ValueError("plan_store required for resume")
        plan = plan_store.get(plan_id)
        if not plan:
            raise ValueError(f"plan not found: {plan_id}")
        last_done = plan_store.get_last_done_step(plan_id)
        start_from = last_done + 1 if last_done else 1
        plan_store.update_status(plan_id, PlanStatus.EXECUTING)
        plan.status = PlanStatus.EXECUTING
        return await self.execute(
            plan,
            session_id,
            channel,
            workspace_path=workspace_path,
            plan_id=plan_id,
            plan_store=plan_store,
            start_from_step_id=start_from,
            skill_id=plan.skill_id,
            skill_registry=skill_registry,
            audit_store=audit_store,
            verification_gate=verification_gate,
        )

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
            # 危险命令检查
            cmd_str = str(args.get("cmd", args.get("command", ""))) + json.dumps(args, ensure_ascii=False)
            is_dangerous = any(dc in cmd_str for dc in DANGEROUS_COMMANDS)
            if is_dangerous:
                await channel.send(session_id, {
                    "type": "confirmation_needed",
                    "session_id": session_id,
                    "step_id": step.id,
                    "command": cmd_str[:200],
                    "risk_level": "critical" if ("rm -rf" in cmd_str or "> /dev/sd" in cmd_str) else "high",
                    "message": f"危险命令: {cmd_str[:100]}",
                    "timestamp": now_iso(),
                })
                # 等待确认（复用现有决策机制）
                decision = await self.act_policy.ask_user(step_dict, session_id, channel)
                if decision != ActDecision.RETRY:
                    return ToolResult(success=False, output="", error="用户拒绝执行危险命令")

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
                await channel.send(session_id, {
                    "type": "step_verified",
                    "session_id": session_id,
                    "step_id": step.id,
                    "message": verify_result.message,
                    "timestamp": now_iso(),
                })
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
            await channel.send(session_id, {
                "type": "task_aborted",
                "session_id": session_id,
                "step_id": step.id,
                "error": verify_result.message,
                "timestamp": now_iso(),
            })
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
