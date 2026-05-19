"""SkillRouter — v2.2 动态技能路由（v4.1 内容匹配）"""
import asyncio
import importlib
from typing import Any, Dict, List, Optional

from tars.skills.base import Skill, SkillType
from tars.skills.registry import SkillRegistry
from tars.skills.context import SkillContext
from tars.skills.signal_extractor import extract_signals


class SkillRouter:
    """基于 scene 动态激活技能，替代永久注入"""

    def __init__(self, skill_registry: SkillRegistry, config=None):
        self.registry = skill_registry
        self.config = config  # SkillsConfig or MemoryConfig
        self._forced_sticky: Dict[str, str] = {}
        self._forced_off: set = set()

    @property
    def top_k(self) -> int:
        return getattr(self.config, "skill_top_k", None) or 3

    @property
    def min_score(self) -> float:
        return getattr(self.config, "skill_min_score", None) or 0.25

    def route_from_content(self, user_content: str, tenant_id: Optional[str] = None) -> List[tuple]:
        """Sync route: trigger rules + content keyword matching."""
        if not user_content:
            return []

        intent, entities, keywords = extract_signals(user_content)
        candidates: Dict[str, tuple] = {}

        for skill, score in self.route(intent, entities, keywords, tenant_id=tenant_id):
            candidates[skill.registry_key] = (skill, score)

        content_lower = user_content.lower()
        for skill in self.registry.list_prompt_skills(tenant_id):
            if skill.registry_key in self._forced_off or skill.id in self._forced_off:
                continue
            if self._is_archived(skill.id):
                continue
            if skill.registry_key in candidates:
                continue
            score = self._score_content_relevance(skill, content_lower, keywords)
            if score >= self.min_score:
                candidates[skill.registry_key] = (skill, score)

        for skill_id in self._forced_sticky:
            skill = self.registry.get(skill_id, tenant_id)
            if skill and skill.id not in self._forced_off and skill.registry_key not in self._forced_off:
                candidates[skill.registry_key] = (skill, 1.0)

        ranked = sorted(candidates.values(), key=lambda x: x[1], reverse=True)
        return ranked[: self.top_k]

    def build_injection(self, matched: List[tuple]) -> str:
        sections = []
        for skill, _ in matched:
            if skill.prompt_template:
                sections.append(f"## 已激活技能: {skill.name}\n{skill.prompt_template}")
        return "\n\n".join(sections)

    def _is_archived(self, skill_id: str) -> bool:
        try:
            from .curator import skill_curator
            return bool(skill_curator and skill_curator.is_archived(skill_id))
        except ImportError:
            return False

    @staticmethod
    def _score_content_relevance(skill: Skill, content_lower: str, keywords: List[str]) -> float:
        score = 0.0
        name = (skill.name or "").lower()
        desc = (getattr(skill, "description", "") or "").lower()
        skill_id = (skill.id or "").lower()

        if name and name in content_lower:
            score += 1.0
        if skill_id and skill_id.replace("_", "-") in content_lower:
            score += 0.8
        if skill_id and skill_id.replace("_", " ") in content_lower:
            score += 0.8

        for tag in getattr(skill, "tags", []) or []:
            if tag.lower() in content_lower:
                score += 0.5

        for kw in getattr(skill, "trigger_keywords", []) or []:
            if kw.lower() in content_lower:
                score += 0.7

        for kw in keywords:
            if kw.lower() in name or kw.lower() in desc or kw.lower() in skill_id:
                score += 0.4

        for token in desc.replace("，", " ").replace("、", " ").split():
            token = token.strip().lower()
            if len(token) >= 2 and token in content_lower:
                score += 0.25

        return score

    def route(self, intent: str, entities: list, keywords: list,
              working_ctx: dict = None, tenant_id: Optional[str] = None) -> List[tuple]:
        """返回 [(Skill, score), ...]，最多 top_k 个"""
        candidates = []
        for skill in self.registry.list_enabled(tenant_id):
            if skill.id in self._forced_off or skill.registry_key in self._forced_off:
                continue
            if self._is_archived(skill.id):
                continue
            if skill.id in self._forced_sticky:
                candidates.append((skill, 1.0))
                continue
            if not hasattr(skill, 'trigger_intents') or not skill.trigger_intents:
                # 无 trigger → 不自动激活
                continue
            score = self._score(skill, intent, entities, keywords)
            min_score = self.min_score
            if score >= min_score:
                candidates.append((skill, score))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[: self.top_k]

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

    def clear_sticky(self, skill_id: str = None):
        if skill_id:
            self._forced_sticky.pop(skill_id, None)
        else:
            self._forced_sticky.clear()

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
