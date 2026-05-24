"""Evolution optimize orchestration."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .apply_engine import ApplyEngine, PromptDiffTooLarge
from .config import get_evolution_config
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

    def _insight_burst_metrics(self, tenant_id: str) -> List[str]:
        burst_cfg = get_evolution_config().insight_burst
        return self.db.count_insight_downvote_burst_metrics(
            tenant_id,
            days=burst_cfg.window_days,
            min_count=burst_cfg.min_downvotes,
        )

    def _build_eval_context(self, tenant_id: str) -> Dict[str, Any]:
        history = self.evaluator.history
        last = history[-1] if history else None
        last_ctx = (last.context if last else {}) or {}
        subagent_cfg = self.apply_engine.read_subagent_config(tenant_id)
        master_prompt = self.apply_engine.read_prompt(tenant_id, "master")
        return {
            "personality": self.apply_engine.read_personality_params(tenant_id),
            "prompt_overlay": master_prompt,
            "prompts": {"master": master_prompt},
            "delegation_weights": subagent_cfg.get("delegation_weights") or {},
            "tools_used": last_ctx.get("tools_used") or (last.tools_used if last else []),
            "skill_id": last_ctx.get("skill_id"),
            "subagent": last_ctx.get("subagent_used") or (last.subagent_used if last else None),
        }

    def optimize(self, tenant_id: str = "default") -> Dict[str, Any]:
        burst_metrics = self._insight_burst_metrics(tenant_id)
        recent_events = self.feedback.count_recent(tenant_id, days=7)
        if recent_events < self.min_events and not burst_metrics:
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
        if burst_metrics:
            results["insight_burst"] = burst_metrics

        before_ctx = self._build_eval_context(tenant_id)
        before_eval = self.eval_runner.run(before_ctx)
        batch_id = self.apply_engine.begin_batch()
        results["batch_id"] = batch_id

        if len(history) >= 20 or burst_metrics:
            if not burst_metrics:
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
                sa_personality = self.subagent_optimizer.optimize_personality_weights(history)
                subagent_patch: Dict[str, Any] = {}
                if sa_weights:
                    subagent_patch["delegation_weights"] = sa_weights
                if sa_personality:
                    subagent_patch["personality_weights"] = sa_personality
                if subagent_patch:
                    sa_record = self.apply_engine.apply_subagent_config(tenant_id, subagent_patch)
                    results["apply_records"].append(sa_record.id)
                results["subagent_optimized"] = bool(subagent_patch)
                results["subagent_weights"] = sa_weights
                results["subagent_personality"] = sa_personality

            prompt_types = ["master", "code", "writing", "data", "research", "plan"]
            if burst_metrics:
                prompt_types = ["master", "data"]
            prompt_apply_ids: list[str] = []
            for prompt_type in prompt_types:
                before_prompt = self.prompt_tuner.get_current_prompt(prompt_type, tenant_id, self.apply_engine)
                tuned = self.prompt_tuner.tune_system_prompt(
                    history, prompt_type, tenant_id, self.apply_engine
                )
                if tuned and tuned != before_prompt:
                    try:
                        record = self.apply_engine.apply_prompt(tenant_id, prompt_type, tuned)
                        prompt_apply_ids.append(record.id)
                    except PromptDiffTooLarge:
                        logger.warning("prompt diff too large for %s, skipped", prompt_type)
                        try:
                            from ..security.audit import safe_audit

                            safe_audit(
                                lambda logger: logger.log(
                                    action="prompt_diff_too_large",
                                    resource_type="prompt",
                                    resource_id=prompt_type,
                                    tenant_id=tenant_id,
                                    user_id="system",
                                    detail=f"tenant={tenant_id} prompt={prompt_type}",
                                )
                            )
                        except Exception:
                            pass
            if prompt_apply_ids:
                results["prompts_tuned"] = True
                results["prompt_apply_records"] = prompt_apply_ids
                results["apply_records"].extend(prompt_apply_ids)

        results["skill_suggestions"] = self.skill_optimizer.suggest_patches()
        skill_apply_ids: list[str] = []
        for sug in results["skill_suggestions"]:
            skill_path = self.apply_engine.resolve_skill_md_path(sug["skill_id"])
            if not skill_path:
                continue
            try:
                from tars.skills.skill_md_parser import parse_skill_md

                smd = parse_skill_md(skill_path)
                base = (smd.description if smd else "") or ""
                note = f" (evolution: clarify usage — success rate {sug.get('success_rate', 0):.0%})"
                if note.strip() in base:
                    continue
                new_desc = (base + note).strip()
                record = self.apply_engine.apply_skill_description(
                    tenant_id,
                    sug["skill_id"],
                    new_desc,
                    skill_md_path=skill_path,
                )
                skill_apply_ids.append(record.id)
            except Exception:
                logger.exception("skill description apply failed skill_id=%s", sug.get("skill_id"))
        if skill_apply_ids:
            results["skill_applied"] = len(skill_apply_ids)
            results["skill_apply_records"] = skill_apply_ids
            results["apply_records"].extend(skill_apply_ids)

        after_ctx = self._build_eval_context(tenant_id)
        after_eval = self.eval_runner.run(after_ctx)
        comparison = self.eval_runner.compare(before_eval, after_eval)
        results["eval"] = comparison

        if comparison.get("should_rollback") and results["apply_records"]:
            rolled = self.apply_engine.rollback_batch(batch_id)
            if rolled:
                results["rolled_back"] = rolled
                logger.warning("Evolution eval gate rollback batch_id=%s count=%s", batch_id, len(rolled))

        return results
