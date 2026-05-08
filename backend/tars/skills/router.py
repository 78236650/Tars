"""SkillRouter — v2.2 动态技能路由"""
import asyncio
import importlib
from typing import Any, Dict, List, Optional

from tars.skills.base import Skill, SkillType
from tars.skills.registry import SkillRegistry
from tars.skills.context import SkillContext


class SkillRouter:
    """基于 scene 动态激活技能，替代永久注入"""

    def __init__(self, skill_registry: SkillRegistry, config=None):
        self.registry = skill_registry
        self.config = config  # MemoryConfig
        self._forced_sticky: Dict[str, str] = {}  # skill_id -> "sticky"
        self._forced_off: set = set()

    def route(self, intent: str, entities: list, keywords: list,
              working_ctx: dict = None) -> List[tuple]:
        """返回 [(Skill, score), ...]，最多 top_k 个"""
        candidates = []
        for skill in self.registry.list_enabled():
            if skill.id in self._forced_off:
                continue
            if skill.id in self._forced_sticky:
                candidates.append((skill, 1.0))
                continue
            if not hasattr(skill, 'trigger_intents') or not skill.trigger_intents:
                # 无 trigger → 不自动激活
                continue
            score = self._score(skill, intent, entities, keywords)
            min_score = self.config.skill_min_score if self.config else 0.3
            if score >= min_score:
                candidates.append((skill, score))

        top_k = self.config.skill_top_k if self.config else 3
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]

    def _score(self, skill: Skill, intent: str, entities: list, keywords: list) -> float:
        intent_score = self._match_intent(skill, intent)
        entity_score = self._match_entities(skill, entities)
        kw_score = self._match_keywords(skill, keywords)

        conditions = getattr(skill, 'trigger_conditions', 'any')
        if conditions == 'all':
            if not intent_score or not entity_score or not kw_score:
                return 0

        return intent_score * 0.5 + entity_score * 0.3 + kw_score * 0.2

    def _match_intent(self, skill: Skill, intent: str) -> float:
        if not hasattr(skill, 'trigger_intents') or not skill.trigger_intents:
            return 0
        for ti in skill.trigger_intents:
            if ti == intent:
                return 1.0
            if ti.endswith('.*') and intent.startswith(ti[:-2]):
                return 0.7
        return 0

    def _match_entities(self, skill: Skill, entities: list) -> float:
        if not hasattr(skill, 'trigger_entities') or not skill.trigger_entities:
            return 0
        matched = 0
        for e in entities:
            if e in skill.trigger_entities:
                matched += 1
        return min(1.0, matched * 0.5)

    def _match_keywords(self, skill: Skill, keywords: list) -> float:
        if not hasattr(skill, 'trigger_keywords') or not skill.trigger_keywords:
            return 0
        for kw in keywords:
            for tk in skill.trigger_keywords:
                if kw in tk or tk in kw:
                    return 1.0
        return 0

    def force_sticky(self, skill_id: str):
        self._forced_sticky[skill_id] = "sticky"
        self._forced_off.discard(skill_id)

    def force_off(self, skill_id: str):
        self._forced_off.add(skill_id)
        self._forced_sticky.pop(skill_id, None)

    def clear_overrides(self):
        self._forced_sticky.clear()
        self._forced_off.clear()

    # ---- Hooks 执行 ----

    async def run_hooks(self, skill: Skill, ctx: SkillContext, phase: str) -> SkillContext:
        """执行指定 phase 的 hook。phase: on_activate|pre_llm|post_llm"""
        if not hasattr(skill, 'hooks') or not skill.hooks:
            return ctx
        hook_spec = skill.hooks.get(phase)
        if not hook_spec:
            return ctx

        try:
            module_path, func_name = hook_spec.rsplit(":", 1)
            module = importlib.import_module(module_path.replace("/", "."))
            fn = getattr(module, func_name)
            result = await asyncio.wait_for(fn(ctx), timeout=2.0)
            return result if result else ctx
        except asyncio.TimeoutError:
            print(f"[SkillRouter] Hook {skill.id}:{phase} 超时")
        except Exception as e:
            print(f"[SkillRouter] Hook {skill.id}:{phase} 失败: {e}")
        return ctx
