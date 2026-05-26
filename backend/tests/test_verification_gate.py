"""M3 — Verification Gate tests"""
import asyncio

import pytest

from tars.config.verification import VerificationConfig
from tars.orchestration.verification import (
    CommandResult,
    ExpectEvaluator,
    VerificationGate,
    VerifyStep,
)


class TestExpectEvaluator:
    def test_exit_code(self):
        ev = ExpectEvaluator()
        ok = CommandResult(exit_code=0, stdout="", stderr="", duration_ms=10)
        bad = CommandResult(exit_code=1, stdout="", stderr="", duration_ms=10)
        assert ev.evaluate("exit_code == 0", ok) is True
        assert ev.evaluate("exit_code == 0", bad) is False

    def test_stdout_contains(self):
        ev = ExpectEvaluator()
        r = CommandResult(exit_code=0, stdout="hello OK world", stderr="", duration_ms=5)
        assert ev.evaluate('stdout contains "OK"', r) is True
        assert ev.evaluate('stdout not contains "ERROR"', r) is True
        assert ev.evaluate('stdout contains "MISSING"', r) is False

    def test_duration_ms(self):
        ev = ExpectEvaluator()
        r = CommandResult(exit_code=0, stdout="", stderr="", duration_ms=1200)
        assert ev.evaluate("duration_ms < 5000", r) is True
        assert ev.evaluate("duration_ms < 500", r) is False

    def test_status_code_from_stdout(self):
        ev = ExpectEvaluator()
        r = CommandResult(exit_code=0, stdout="200", stderr="", duration_ms=1)
        assert ev.evaluate("status_code == 200", r) is True


class TestVerificationGate:
    @pytest.mark.asyncio
    async def test_strict_all_pass(self):
        gate = VerificationGate(VerificationConfig({"enabled": True, "default_mode": "strict"}))
        steps = [
            VerifyStep(command="echo OK", expect='stdout contains "OK"', timeout_sec=5),
            VerifyStep(command="exit 0", expect="exit_code == 0", timeout_sec=5),
        ]
        result = await gate.run(steps, mode="strict")
        assert result.passed is True
        assert result.status == "pass"
        assert len(result.step_results) == 2
        assert all(s.passed for s in result.step_results)

    @pytest.mark.asyncio
    async def test_strict_one_fail(self):
        gate = VerificationGate(VerificationConfig({"enabled": True}))
        steps = [
            VerifyStep(command="exit 0", expect="exit_code == 0", timeout_sec=5),
            VerifyStep(command="exit 1", expect="exit_code == 0", timeout_sec=5),
        ]
        result = await gate.run(steps, mode="strict")
        assert result.passed is False
        assert result.status == "fail"

    @pytest.mark.asyncio
    async def test_lenient_partial_pass(self):
        cfg = VerificationConfig({"enabled": True, "lenient_pass_rate": 0.5})
        gate = VerificationGate(cfg)
        steps = [
            VerifyStep(command="exit 0", expect="exit_code == 0", timeout_sec=5),
            VerifyStep(command="exit 1", expect="exit_code == 0", timeout_sec=5),
        ]
        result = await gate.run(steps, mode="lenient")
        assert result.passed is True
        assert result.status == "done_with_warnings"

    @pytest.mark.asyncio
    async def test_lenient_below_threshold(self):
        cfg = VerificationConfig({"enabled": True, "lenient_pass_rate": 0.8})
        gate = VerificationGate(cfg)
        steps = [
            VerifyStep(command="exit 0", expect="exit_code == 0", timeout_sec=5),
            VerifyStep(command="exit 1", expect="exit_code == 0", timeout_sec=5),
        ]
        result = await gate.run(steps, mode="lenient")
        assert result.passed is False
        assert result.status == "fail"

    @pytest.mark.asyncio
    async def test_disabled_skips(self):
        gate = VerificationGate(VerificationConfig({"enabled": False}))
        steps = [VerifyStep(command="exit 1", expect="exit_code == 0", timeout_sec=5)]
        result = await gate.run(steps, mode="strict")
        assert result.passed is True
        assert result.status == "skipped"

    @pytest.mark.asyncio
    async def test_command_timeout(self):
        gate = VerificationGate(VerificationConfig({"enabled": True}))
        steps = [VerifyStep(command="sleep 5", expect="exit_code == 0", timeout_sec=1)]
        result = await gate.run(steps, mode="strict")
        assert result.passed is False
        assert "timeout" in result.step_results[0].message.lower()


class TestSkillVerifyLoading:
    def test_deploy_skill_has_verify(self):
        from pathlib import Path
        from tars.skills.skill_md_parser import parse_skill_md

        path = Path(__file__).resolve().parent.parent.parent / "skills" / "_global" / "deploy" / "SKILL.md"
        smd = parse_skill_md(str(path))
        assert smd.verify_mode == "strict"
        assert len(smd.verify) >= 1
        assert smd.verify[0]["command"]
