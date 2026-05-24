"""Evolution eval set runner for optimize gate."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class EvalRunner:
    def __init__(self, eval_path: Optional[Path] = None):
        self.eval_path = eval_path or Path(__file__).resolve().parents[2] / "tests" / "evolution" / "eval_set.yaml"

    def load_cases(self) -> List[Dict[str, Any]]:
        if not self.eval_path.exists():
            return []
        raw = yaml.safe_load(self.eval_path.read_text(encoding="utf-8")) or {}
        return raw.get("cases") or []

    def score_case(self, case: Dict[str, Any], context: Dict[str, Any]) -> float:
        category = case.get("category", "")
        expected = case.get("expected", "")
        score = 0.0
        if category == "personality_match":
            params = context.get("personality") or {}
            for key, target in (case.get("expect_params") or {}).items():
                val = params.get(key)
                if val is not None and abs(float(val) - float(target)) <= 0.15:
                    score += 1.0
            denom = max(len(case.get("expect_params") or {}), 1)
            return score / denom
        if category == "tool_choice":
            tools = context.get("tools_used") or []
            if expected in tools:
                return 1.0
            return 0.0
        if category == "skill_route":
            if context.get("skill_id") == expected:
                return 1.0
            return 0.0
        if category == "subagent_delegate":
            if context.get("subagent") == expected:
                return 1.0
            return 0.0
        return 0.5 if context.get("matched") else 0.0

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        cases = self.load_cases()
        if not cases:
            return {"score": 0.0, "total": 0, "passed": 0}
        scores = [self.score_case(c, context) for c in cases]
        total = len(scores)
        passed = sum(1 for s in scores if s >= 0.5)
        avg = sum(scores) / total if total else 0.0
        return {"score": avg, "total": total, "passed": passed}

    def compare(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        b = before.get("score", 0.0)
        a = after.get("score", 0.0)
        delta = a - b
        improved = delta >= 0.10
        rollback = delta < -0.05
        return {
            "before": b,
            "after": a,
            "delta": delta,
            "improved": improved,
            "should_rollback": rollback,
        }
