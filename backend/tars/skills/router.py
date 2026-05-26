"""SkillRouter — v4.3.2 Superpowers-style routing (triggers / skip_when / embedding)"""
import asyncio
import importlib
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from tars.skills.base import Skill, SkillType
from tars.skills.registry import SkillRegistry
from tars.skills.context import SkillContext
from tars.skills.signal_extractor import extract_signals
from tars.skills.intent_extractor import Intent, IntentExtractor


@dataclass
class SkillCandidate:
    skill_id: str
    score: float
    match_reason: str
    skill: Optional[Skill] = None


class SkillRouter:
    """基于 triggers / skip_when / embedding 动态激活技能。"""

    def __init__(self, skill_registry: SkillRegistry, config=None, embedding_provider=None):
        self.registry = skill_registry
        self.config = config  # SkillsConfig or MemoryConfig
        self._embedding_provider = embedding_provider
        self._forced_sticky: Dict[str, str] = {}
        self._forced_off: set = set()
        self._skill_embeddings: Dict[str, List[float]] = {}
        self._embedding_built_at: float = 0.0
        self._intent_extractor = IntentExtractor(
            embedding_provider=embedding_provider,
            use_embedding=self.use_embedding,
        )

    @property
    def top_k(self) -> int:
        return getattr(self.config, "skill_top_k", None) or 3

    @property
    def min_score(self) -> float:
        return getattr(self.config, "skill_min_score", None) or 0.25

    @property
    def use_embedding(self) -> bool:
        return bool(getattr(self.config, "use_embedding", True))

    @property
    def cache_ttl_sec(self) -> int:
        return int(getattr(self.config, "cache_ttl_sec", 300))

    def _ensure_skill_embeddings(self, tenant_id: Optional[str] = None) -> None:
        if not self.use_embedding or not self._embedding_provider:
            return
        now = time.time()
        if self._skill_embeddings and (now - self._embedding_built_at) < self.cache_ttl_sec:
            return
        texts = []
        keys = []
        for skill in self.registry.list_enabled(tenant_id):
            triggers = self._effective_triggers(skill)
            if not triggers and not skill.description:
                continue
            text = " ".join(triggers) + " " + (skill.description or "") + " " + (skill.name or "")
            texts.append(text.strip())
            keys.append(skill.registry_key)
        if not texts:
            return
        try:
            vectors = self._embedding_provider.encode(texts)
            self._skill_embeddings = {k: v for k, v in zip(keys, vectors)}
            self._embedding_built_at = now
        except Exception:
            self._skill_embeddings = {}

    @staticmethod
    def _effective_triggers(skill: Skill) -> List[str]:
        triggers = list(getattr(skill, "triggers", None) or [])
        if triggers:
            return triggers
        for ti in getattr(skill, "trigger_intents", None) or []:
            prefix = ti if str(ti).startswith("intent:") else f"intent:{ti}"
            triggers.append(prefix)
        triggers.extend(getattr(skill, "trigger_keywords", None) or [])
        return triggers

    @staticmethod
    def _is_regex_pattern(pattern: str) -> bool:
        if pattern.startswith("intent:") or pattern.startswith("context:"):
            return False
        return any(ch in pattern for ch in (".*", "+", "?", "[", "(", "|", "^", "$"))

    @staticmethod
    def _normalize_intent(label: str) -> str:
        return (label or "").replace("_", ".").replace("-", ".").lower()

    def _pattern_matches(self, pattern: str, text: str, intent_label: str, context: dict) -> bool:
        if pattern.startswith("intent:"):
            expected = self._normalize_intent(pattern[7:])
            actual = self._normalize_intent(intent_label)
            suffix = expected.rstrip(".*")
            return actual == expected or actual.startswith(suffix)
        if pattern.startswith("context:"):
            key = pattern[8:]
            return bool(context.get(key))
        if self._is_regex_pattern(pattern):
            try:
                return bool(re.search(pattern, text, re.IGNORECASE))
            except re.error:
                return pattern.lower() in text.lower()
        return pattern.lower() in text.lower()

    def _should_skip(self, skill: Skill, text: str, intent_label: str, context: dict,
                     trigger_matched: bool = False) -> bool:
        for rule in getattr(skill, "skip_when", None) or []:
            if rule.startswith("intent:") and trigger_matched:
                continue
            if self._pattern_matches(rule, text, intent_label, context):
                return True
        return False

    def _score_triggers(self, skill: Skill, text: str, intent_label: str) -> Tuple[float, str]:
        triggers = self._effective_triggers(skill)
        if not triggers:
            return 0.0, ""
        best = 0.0
        reason = ""
        for pattern in triggers:
            if self._pattern_matches(pattern, text, intent_label, {}):
                if pattern.startswith("intent:"):
                    score = 0.9
                    hit = f"intent:{pattern[7:]}"
                elif self._is_regex_pattern(pattern):
                    score = 0.85
                    hit = f"regex:{pattern}"
                else:
                    score = 0.8
                    hit = f"keyword:{pattern}"
                if score > best:
                    best = score
                    reason = hit
        return best, reason

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def _score_embedding(self, skill: Skill, intent: Intent) -> Tuple[float, str]:
        if not self.use_embedding or not intent.embedding:
            return 0.0, ""
        vec = self._skill_embeddings.get(skill.registry_key)
        if not vec:
            return 0.0, ""
        sim = self._cosine(intent.embedding, vec)
        if sim <= 0:
            return 0.0, ""
        return sim, f"embedding:{sim:.2f}"

    def match(self, intent: Intent, context: Optional[dict] = None, tenant_id: Optional[str] = None) -> List[SkillCandidate]:
        """Return top-K skill candidates ranked by trigger + embedding + priority."""
        context = context or {}
        text = intent.text or ""
        intent_label = intent.intent_label or "general.chat"

        self._ensure_skill_embeddings(tenant_id)
        candidates: List[SkillCandidate] = []

        for skill in self.registry.list_enabled(tenant_id):
            if skill.id in self._forced_off or skill.registry_key in self._forced_off:
                continue
            if self._is_archived(skill.id):
                continue
            if skill.id in self._forced_sticky:
                candidates.append(SkillCandidate(
                    skill_id=skill.id,
                    score=1.0,
                    match_reason="sticky",
                    skill=skill,
                ))
                continue

            triggers = self._effective_triggers(skill)
            if not triggers:
                continue

            trigger_score, trigger_reason = self._score_triggers(skill, text, intent_label)
            embed_score, embed_reason = self._score_embedding(skill, intent)

            if self._should_skip(skill, text, intent_label, context, trigger_matched=trigger_score > 0):
                continue

            if trigger_score > 0 and embed_score > 0:
                score = trigger_score * 0.6 + embed_score * 0.4
                reason = f"{trigger_reason}+{embed_reason}"
            elif trigger_score > 0:
                score = trigger_score
                reason = trigger_reason
            elif embed_score > 0:
                score = embed_score
                reason = embed_reason
            else:
                continue

            score += (getattr(skill, "priority", 50) or 50) / 1000.0
            if score < self.min_score:
                continue

            candidates.append(SkillCandidate(
                skill_id=skill.id,
                score=score,
                match_reason=reason,
                skill=skill,
            ))

        candidates.sort(key=lambda c: (c.score, getattr(c.skill, "priority", 50)), reverse=True)
        return candidates[: self.top_k]

    def build_recommendations(self, candidates: List[SkillCandidate]) -> str:
        if not candidates:
            return ""
        lines = ["## 推荐技能 (Router)", "以下技能由路由匹配，你可选择是否采用：", ""]
        for c in candidates:
            lines.append(f"- **{c.skill_id}** (score={c.score:.2f}, {c.match_reason})")
        return "\n".join(lines)

    def route_from_content(
        self,
        user_content: str,
        tenant_id: Optional[str] = None,
        scene_intent: Optional[str] = None,
        scene_keywords: Optional[List[str]] = None,
        context: Optional[dict] = None,
    ) -> List[tuple]:
        """Sync route: v4.3.2 match + legacy content keyword fallback."""
        if not user_content:
            return []

        intent = self._intent_extractor.extract(user_content)
        if scene_intent and scene_intent not in ("unknown", "casual", "meta", ""):
            intent.intent_label = scene_intent
        if scene_keywords:
            intent.keywords = list({*intent.keywords, *[k for k in scene_keywords if k]})

        candidates: Dict[str, tuple] = {}

        for cand in self.match(intent, context=context, tenant_id=tenant_id):
            if cand.skill:
                candidates[cand.skill.registry_key] = (cand.skill, cand.score)

        legacy_intent, legacy_entities, legacy_keywords = extract_signals(user_content)
        if scene_intent and scene_intent not in ("unknown", "casual", "meta", ""):
            legacy_intent = scene_intent
        if scene_keywords:
            legacy_keywords = list({*legacy_keywords, *[k for k in scene_keywords if k]})

        for skill, score in self.route(legacy_intent, legacy_entities, legacy_keywords, tenant_id=tenant_id):
            if skill.registry_key not in candidates:
                candidates[skill.registry_key] = (skill, score)

        content_lower = user_content.lower()
        for skill in self.registry.list_prompt_skills(tenant_id):
            if skill.registry_key in self._forced_off or skill.id in self._forced_off:
                continue
            if self._is_archived(skill.id):
                continue
            if skill.registry_key in candidates:
                continue
            score = self._score_content_relevance(skill, content_lower, intent.keywords)
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
        """Legacy route via trigger_intents (skill.yaml)."""
        candidates = []
        for skill in self.registry.list_enabled(tenant_id):
            if skill.id in self._forced_off or skill.registry_key in self._forced_off:
                continue
            if self._is_archived(skill.id):
                continue
            if skill.id in self._forced_sticky:
                candidates.append((skill, 1.0))
                continue
            if self._effective_triggers(skill):
                continue
            if not hasattr(skill, 'trigger_intents') or not skill.trigger_intents:
                continue
            score = self._score(skill, intent, entities, keywords)
            if score >= self.min_score:
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
