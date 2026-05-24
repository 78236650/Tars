"""Evolution optimize orchestration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .apply_engine import ApplyEngine
from .eval_runner import EvalRunner
from .feedback_collector import FeedbackCollector
from .skill_optimizer import SkillOptimizer

logger = logging.getLogger(__name__)


class EvolutionOrchestrator:
    def __init__(
        self,
        db,
        *,
        feedback_collector: FeedbackCollector,
        apply_engine: ApplyEngine,
        personality_optimizer,
        subagent_optimizer,
        prompt_tuner,
        evaluator,
        min_events: int = 20,
        confidence_threshold: float = 0.05,
    ):
        self.db = db
        self.feedback = feedback_collector
        self.apply_engine = apply_engine
        self.personality_optimizer = personality_optimizer
        self.subagent_optimizer = subagent_optimizer
        self.prompt_tuner = prompt_tuner
        self.evaluator = evaluator
        self.skill_optimizer = SkillOptimizer(db)
        self.eval_runner = EvalRunner()
        self.min_events = min_events
        self.confidence_threshold = confidence_threshold

    def optimize(self, tenant_id: str = "default") -> Dict[str, Any]:
        if self.feedback.count_recent(tenant_id, days=7) < self.min_events:
            return {"skipped": True, "reason": "insufficient_events", "tenant_id": tenant_id}

        history = self.evaluator.history
        results: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "skipped": False,
            "personality_optimized": False,
            "prompts_tuned": False,
            "subagent_optimized": False,
            "skill_suggestions": [],
            "apply_records": [],
        }

        before_ctx = {"personality": self.apply_engine.read_personality_params(tenant_id)}
        before_eval = self.eval_runner.run(before_ctx)

        if len(history) >= 20:
            current = before_ctx["personality"]
            suggested = self.personality_optimizer.optimize(current, history)
            delta_keys = [
                k for k, v in suggested.items()
                if k in current and abs(float(v) - float(current[k])) >= self.confidence_threshold
            ]
            if delta_keys:
                patch = {k: suggested[k] for k in delta_keys}
                record = self.apply_engine.apply_personality(tenant_id, patch)
                results["personality_optimized"] = True
                results["apply_records"].append(record.id)
                results["new_personality"] = patch

            sa_weights = self.subagent_optimizer.optimize_task_delegation(history)
            results["subagent_optimized"] = True
            results["subagent_weights"] = sa_weights

            for prompt_type in ["master", "code", "writing", "data", "research", "plan"]:
                self.prompt_tuner.tune_system_prompt(history, prompt_type)
            results["prompts_tuned"] = True

        results["skill_suggestions"] = self.skill_optimizer.suggest_patches()

        after_ctx = {"personality": self.apply_engine.read_personality_params(tenant_id)}
        after_eval = self.eval_runner.run(after_ctx)
        comparison = self.eval_runner.compare(before_eval, after_eval)
        results["eval"] = comparison

        if comparison.get("should_rollback") and results["apply_records"]:
            last_id = results["apply_records"][-1]
            if self.apply_engine.rollback(last_id):
                results["rolled_back"] = last_id
                logger.warning("Evolution eval gate rollback apply_id=%s", last_id)

        return results
