"""StepVerifier — v2.4 步骤验证器（Check 阶段）

支持 6 种验证类型：exit_code, output_contains, output_not_contains,
                  file_exists, file_not_exists, custom
"""
import re
from pathlib import Path
from typing import Any, Dict, Optional

from ..tools.base import ToolResult


class VerifyResult:
    def __init__(self, passed: bool, message: str = ""):
        self.passed = passed
        self.message = message


class StepVerifier:
    """步骤执行后验证结果"""

    def check(self, step: dict, result: ToolResult, workspace_path: str = ".") -> VerifyResult:
        """对步骤执行结果进行验证。

        step: 包含 verify 字段的步骤字典
              { verify: { type: "exit_code", expected: 0, error_msg: "..." } }
        result: 工具执行结果
        workspace_path: 工作区路径（file_exists 验证需要）

        若 verify 字段缺失 → 默认 exit_code == 0
        """
        verify = step.get("verify") or {}
        vtype = verify.get("type", "exit_code")
        expected = verify.get("expected")
        error_msg = verify.get("error_msg", "")

        if vtype == "exit_code":
            return self._check_exit_code(result, expected, error_msg)
        if vtype == "output_contains":
            return self._check_output_contains(result, expected, error_msg)
        if vtype == "output_not_contains":
            return self._check_output_not_contains(result, expected, error_msg)
        if vtype == "file_exists":
            return self._check_file_exists(expected, workspace_path, error_msg)
        if vtype == "file_not_exists":
            return self._check_file_not_exists(expected, workspace_path, error_msg)
        if vtype == "custom":
            return VerifyResult(True, "custom verify: skipped (LLM 判断由上层处理)")

        # 未知验证类型 → 默认通过
        return VerifyResult(True, f"unknown verify type: {vtype}")

    def _check_exit_code(self, result: ToolResult, expected, error_msg: str) -> VerifyResult:
        want = int(expected) if expected is not None else 0
        code = result.metadata.get("returncode", 0) if result.metadata else 0
        if result.success and code == want:
            return VerifyResult(True, f"exit_code={code} ✓")
        return VerifyResult(False, error_msg or f"exit_code={code} (expected {want})")

    def _check_output_contains(self, result: ToolResult, expected, error_msg: str) -> VerifyResult:
        if not expected:
            return VerifyResult(True, "skip (no expected value)")
        output = (result.output or "") + (result.error or "")
        if expected in output:
            return VerifyResult(True, f"output contains '{expected[:40]}' ✓")
        return VerifyResult(False, error_msg or f"output missing '{expected[:40]}'")

    def _check_output_not_contains(self, result: ToolResult, expected, error_msg: str) -> VerifyResult:
        if not expected:
            return VerifyResult(True, "skip (no expected value)")
        output = (result.output or "") + (result.error or "")
        if expected not in output:
            return VerifyResult(True, f"output does not contain '{expected[:40]}' ✓")
        return VerifyResult(False, error_msg or f"output contains forbidden '{expected[:40]}'")

    def _check_file_exists(self, expected, workspace_path: str, error_msg: str) -> VerifyResult:
        if not expected:
            return VerifyResult(True, "skip (no expected path)")
        path = Path(workspace_path) / expected
        if path.exists():
            return VerifyResult(True, f"file exists: {expected} ✓")
        return VerifyResult(False, error_msg or f"file not found: {expected}")

    def _check_file_not_exists(self, expected, workspace_path: str, error_msg: str) -> VerifyResult:
        if not expected:
            return VerifyResult(True, "skip (no expected path)")
        path = Path(workspace_path) / expected
        if not path.exists():
            return VerifyResult(True, f"file not exists: {expected} ✓")
        return VerifyResult(False, error_msg or f"file still exists: {expected}")


# 全局单例
verifier = StepVerifier()
