"""Verification Gate — post-execution command checks (v4.3.2)"""
import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

from ..config.verification import VerificationConfig, verification_config
from ..skills.base import VerifyStep


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


@dataclass
class VerifyStepResult:
    command: str
    expect: str
    passed: bool
    message: str
    exit_code: int = 0
    duration_ms: int = 0


@dataclass
class VerifyResult:
    passed: bool
    status: str
    step_results: List[VerifyStepResult] = field(default_factory=list)


class ExpectEvaluator:
    _COMPARE = re.compile(
        r"^(exit_code|duration_ms|status_code)\s*(==|!=|<|>|<=|>=)\s*(-?\d+)$"
    )
    _CONTAINS = re.compile(r'^stdout\s+contains\s+"([^"]+)"$')
    _NOT_CONTAINS = re.compile(r'^stdout\s+not contains\s+"([^"]+)"$')

    def evaluate(self, expect: str, result: CommandResult) -> bool:
        expect = (expect or "exit_code == 0").strip()
        m = self._COMPARE.match(expect)
        if m:
            field_name, op, raw = m.group(1), m.group(2), int(m.group(3))
            if field_name == "exit_code":
                value = result.exit_code
            elif field_name == "duration_ms":
                value = result.duration_ms
            else:
                text = (result.stdout or "").strip()
                value = int(text) if text.isdigit() else -1
            return self._compare(value, op, raw)

        m = self._CONTAINS.match(expect)
        if m:
            return m.group(1) in (result.stdout or "")

        m = self._NOT_CONTAINS.match(expect)
        if m:
            return m.group(1) not in (result.stdout or "")

        return result.exit_code == 0

    @staticmethod
    def _compare(value: int, op: str, target: int) -> bool:
        if op == "==":
            return value == target
        if op == "!=":
            return value != target
        if op == "<":
            return value < target
        if op == ">":
            return value > target
        if op == "<=":
            return value <= target
        if op == ">=":
            return value >= target
        return False


class VerificationGate:
    def __init__(self, config: Optional[VerificationConfig] = None):
        self.config = config or verification_config
        self.evaluator = ExpectEvaluator()

    async def run(
        self,
        verify_steps: List[VerifyStep],
        mode: Optional[str] = None,
        cwd: str = ".",
    ) -> VerifyResult:
        if not self.config.enabled or not verify_steps:
            return VerifyResult(passed=True, status="skipped", step_results=[])

        effective_mode = (mode or self.config.default_mode or "strict").lower()
        step_results: List[VerifyStepResult] = []

        for step in verify_steps:
            cmd_result = await self._run_command(step.command, cwd=cwd, timeout_sec=step.timeout_sec)
            passed = self.evaluator.evaluate(step.expect, cmd_result)
            message = "ok" if passed else f"expect '{step.expect}' failed (exit={cmd_result.exit_code})"
            if "timeout" in (cmd_result.stderr or "").lower():
                message = "command timeout"
            step_results.append(VerifyStepResult(
                command=step.command,
                expect=step.expect,
                passed=passed,
                message=message,
                exit_code=cmd_result.exit_code,
                duration_ms=cmd_result.duration_ms,
            ))

        passed_count = sum(1 for s in step_results if s.passed)
        total = len(step_results)

        if effective_mode == "lenient":
            rate = passed_count / total if total else 0.0
            if rate >= self.config.lenient_pass_rate:
                status = "pass" if passed_count == total else "done_with_warnings"
                return VerifyResult(passed=True, status=status, step_results=step_results)
            return VerifyResult(passed=False, status="fail", step_results=step_results)

        all_pass = passed_count == total
        return VerifyResult(
            passed=all_pass,
            status="pass" if all_pass else "fail",
            step_results=step_results,
        )

    async def _run_command(self, command: str, cwd: str, timeout_sec: int) -> CommandResult:
        start = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=max(1, timeout_sec),
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                elapsed = int((time.perf_counter() - start) * 1000)
                return CommandResult(
                    exit_code=-1,
                    stdout="",
                    stderr="timeout",
                    duration_ms=elapsed,
                )
            elapsed = int((time.perf_counter() - start) * 1000)
            return CommandResult(
                exit_code=proc.returncode or 0,
                stdout=(stdout_b or b"").decode("utf-8", errors="replace"),
                stderr=(stderr_b or b"").decode("utf-8", errors="replace"),
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = int((time.perf_counter() - start) * 1000)
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                duration_ms=elapsed,
            )


_verification_gate: Optional[VerificationGate] = None


def get_verification_gate() -> VerificationGate:
    global _verification_gate
    if _verification_gate is None:
        _verification_gate = VerificationGate()
    return _verification_gate
