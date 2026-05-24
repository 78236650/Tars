"""Evolution eval set runner for optimize gate."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .config import get_evolution_config


class EvalRunner:
    def __init__(self, eval_path: Optional[Path] = None):
        self.eval_path = eval_path or Path(__file__).resolve().parents[2] / "tests" / "evolution" / "eval_set.yaml"

    def load_cases(self) -> List[Dict[str, Any]]:
        if not self.eval_path.exists():
            return []
        raw = yaml.safe_load(self.eval_path.read_text(encoding="utf-8")) or {}
        return raw.get("cases") or []

    def score_case(self, case: Dict[str, Any], context: Dict[str, Any]) -> Optional[float]:
        category = case.get("category", "")
        expected = case.get("expected", "")

        if category == "personality_match":
            params = context.get("personality") or {}
            if not params:
                return None
            score = 0.0
            expect_params = case.get("expect_params") or {}
            if not expect_params:
                return None
            for key, target in expect_params.items():
                val = params.get(key)
                if val is not None and abs(float(val) - float(target)) <= 0.15:
                    score += 1.0
            return score / max(len(expect_params), 1)

        if category == "tool_choice":
            tools = context.get("tools_used") or []
            if not tools:
                return None
            return 1.0 if expected in tools else 0.0

        if category == "skill_route":
            skill_id = context.get("skill_id")
            if not skill_id:
                return None
            return 1.0 if skill_id == expected else 0.0

        if category == "subagent_delegate":
            subagent = context.get("subagent")
            if not subagent:
                return None
            return 1.0 if subagent == expected else 0.0

        return 0.5 if context.get("matched") else 0.0

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        cases = self.load_cases()
        if not cases:
            return {"score": 0.0, "total": 0, "passed": 0}
        scores: List[float] = []
        for case in cases:
            scored = self.score_case(case, context)
            if scored is not None:
                scores.append(scored)
        total = len(scores)
        passed = sum(1 for s in scores if s >= 0.5)
        avg = sum(scores) / total if total else 0.0
        return {"score": avg, "total": total, "passed": passed}

    def compare(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        gate = get_evolution_config().eval_gate
        b = before.get("score", 0.0)
        a = after.get("score", 0.0)
        delta = a - b
        improved = delta >= gate.improve_min
        rollback = delta < gate.regress_max
        return {
            "before": b,
            "after": a,
            "delta": delta,
            "improved": improved,
            "should_rollback": rollback,
        }
