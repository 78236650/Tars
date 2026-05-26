"""M1 — SkillRouter v4.3.2: triggers / skip_when / embedding match"""
import os
import time
from pathlib import Path

import pytest
import yaml

from tars.config.skills import SkillsConfig
from tars.memory.embeddings import DeterministicEmbeddingProvider
from tars.skills.base import Skill, SkillType
from tars.skills.intent_extractor import IntentExtractor
from tars.skills.registry import SkillRegistry
from tars.skills.router import SkillRouter

EVAL_FIXTURE = Path(__file__).parent / "fixtures" / "skill_routing_eval.yaml"
SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


def _cfg(**overrides):
    data = {
        "router": {
            "enabled": True,
            "top_k": 3,
            "min_score": 0.3,
            "use_embedding": True,
            "embedding_model": "BAAI/bge-small-zh-v1.5",
            "cache_ttl_sec": 300,
        }
    }
    data["router"].update(overrides)
    return SkillsConfig(data)


def _registry(*skills: Skill) -> SkillRegistry:
    reg = SkillRegistry()
    for s in skills:
        reg.register(s)
    return reg


def _load_eval_cases():
    with open(EVAL_FIXTURE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_eval_router(use_embedding: bool = False):
    from tars.skills.loader import SkillLoader
    from tars.tools.registry import ToolRegistry

    reg = SkillRegistry()
    loader = SkillLoader(skills_dir=str(SKILLS_DIR), tool_registry=ToolRegistry(), skill_registry=reg)
    loader.invalidate_cache()
    loader._cache_valid = lambda _: False  # eval always reads fresh frontmatter
    loader.load_all()
    embed = DeterministicEmbeddingProvider()
    cfg = _cfg(use_embedding=use_embedding, min_score=0.25)
    return SkillRouter(reg, cfg, embedding_provider=embed), reg


class TestSkillModelFields:
    def test_triggers_skip_when_defaults(self):
        skill = Skill(id="x", name="x", description="d", type=SkillType.PROMPT)
        assert skill.triggers == []
        assert skill.skip_when == []
        assert skill.priority == 50


class TestTriggerMatching:
    def test_regex_trigger(self):
        reg = _registry(Skill(
            id="bi_query",
            name="bi_query",
            description="BI",
            type=SkillType.PROMPT,
            triggers=["看一下.*指标", "查询数据"],
            priority=80,
        ))
        router = SkillRouter(reg, _cfg(use_embedding=False), DeterministicEmbeddingProvider())
        intent = IntentExtractor(use_embedding=False).extract("帮我看一下销售指标")
        candidates = router.match(intent, {})
        assert len(candidates) >= 1
        assert candidates[0].skill_id == "bi_query"
        assert candidates[0].score >= 0.3

    def test_intent_prefix_trigger(self):
        reg = _registry(Skill(
            id="sql_helper",
            name="sql_helper",
            description="SQL",
            type=SkillType.PROMPT,
            triggers=["intent:data.analyze"],
            priority=70,
        ))
        router = SkillRouter(reg, _cfg(use_embedding=False), DeterministicEmbeddingProvider())
        intent = IntentExtractor(use_embedding=False).extract("随便看看")
        intent.intent_label = "data.analyze"
        candidates = router.match(intent, {})
        assert any(c.skill_id == "sql_helper" for c in candidates)

    def test_legacy_trigger_intents_still_work(self):
        reg = _registry(Skill(
            id="legacy",
            name="legacy",
            description="legacy",
            type=SkillType.PROMPT,
            trigger_intents=["coding.explain"],
            trigger_keywords=["debug"],
        ))
        router = SkillRouter(reg, _cfg(use_embedding=False), DeterministicEmbeddingProvider())
        intent = IntentExtractor(use_embedding=False).extract("帮我 debug 这段代码")
        intent.intent_label = "coding.explain"
        candidates = router.match(intent, {})
        assert any(c.skill_id == "legacy" for c in candidates)


class TestSkipWhen:
    def test_skip_when_blocks_match(self):
        reg = _registry(Skill(
            id="bi_query",
            name="bi_query",
            description="BI",
            type=SkillType.PROMPT,
            triggers=["查询数据"],
            skip_when=["解释.*代码"],
        ))
        router = SkillRouter(reg, _cfg(use_embedding=False), DeterministicEmbeddingProvider())
        intent = IntentExtractor(use_embedding=False).extract("帮我解释这段代码并查询数据")
        candidates = router.match(intent, {})
        assert not any(c.skill_id == "bi_query" for c in candidates)

    def test_context_skip_when(self):
        reg = _registry(Skill(
            id="bi_query",
            name="bi_query",
            description="BI",
            type=SkillType.PROMPT,
            triggers=["查询数据"],
            skip_when=["context:no_datasource"],
        ))
        router = SkillRouter(reg, _cfg(use_embedding=False), DeterministicEmbeddingProvider())
        intent = IntentExtractor(use_embedding=False).extract("查询数据")
        blocked = router.match(intent, {"no_datasource": True})
        allowed = router.match(intent, {"no_datasource": False})
        assert not any(c.skill_id == "bi_query" for c in blocked)
        assert any(c.skill_id == "bi_query" for c in allowed)


class TestPriorityAndTopK:
    def test_priority_breaks_tie(self):
        reg = _registry(
            Skill(
                id="low",
                name="low",
                description="low priority",
                type=SkillType.PROMPT,
                triggers=["报表"],
                priority=30,
            ),
            Skill(
                id="high",
                name="high",
                description="high priority",
                type=SkillType.PROMPT,
                triggers=["报表"],
                priority=90,
            ),
        )
        router = SkillRouter(reg, _cfg(use_embedding=False, top_k=2), DeterministicEmbeddingProvider())
        intent = IntentExtractor(use_embedding=False).extract("生成报表")
        candidates = router.match(intent, {})
        assert candidates[0].skill_id == "high"

    def test_top_k_limit(self):
        skills = [
            Skill(
                id=f"s{i}",
                name=f"s{i}",
                description=f"skill {i}",
                type=SkillType.PROMPT,
                triggers=[f"topic{i}"],
                priority=50 + i,
            )
            for i in range(5)
        ]
        reg = _registry(*skills)
        router = SkillRouter(reg, _cfg(use_embedding=False, top_k=3), DeterministicEmbeddingProvider())
        intent = IntentExtractor(use_embedding=False).extract("topic0 topic1 topic2 topic3")
        candidates = router.match(intent, {})
        assert len(candidates) <= 3


class TestPerformance:
    def test_match_under_50ms(self):
        skills = [
            Skill(
                id=f"s{i}",
                name=f"s{i}",
                description=f"desc {i}",
                type=SkillType.PROMPT,
                triggers=[f"kw{i}", f"pattern{i}.*"],
                skip_when=[f"skip{i}"],
                priority=50,
            )
            for i in range(30)
        ]
        reg = _registry(*skills)
        embed = DeterministicEmbeddingProvider()
        router = SkillRouter(reg, _cfg(), embed)
        extractor = IntentExtractor(embedding_provider=embed)
        intent = extractor.extract("kw5 和其他内容")
        start = time.perf_counter()
        for _ in range(20):
            router.match(intent, {})
        elapsed_ms = (time.perf_counter() - start) / 20 * 1000
        assert elapsed_ms < 50, f"match took {elapsed_ms:.1f}ms"


class TestRouteFromContentCompat:
    def test_route_from_content_still_works(self):
        reg = _registry(Skill(
            id="pdf",
            name="pdf",
            description="PDF manipulation toolkit",
            type=SkillType.PROMPT,
            prompt_template="Use pypdf.",
            enabled=True,
            tags=["pdf"],
        ))
        router = SkillRouter(reg, _cfg(use_embedding=False), DeterministicEmbeddingProvider())
        matched = router.route_from_content("帮我处理这个 PDF 文件")
        assert len(matched) >= 1
        assert matched[0][0].id == "pdf"

    def test_build_recommendations(self):
        reg = _registry(Skill(
            id="bi_query",
            name="bi_query",
            description="BI",
            type=SkillType.PROMPT,
            triggers=["查询数据"],
        ))
        router = SkillRouter(reg, _cfg(use_embedding=False), DeterministicEmbeddingProvider())
        intent = IntentExtractor(use_embedding=False).extract("查询数据")
        candidates = router.match(intent, {})
        text = router.build_recommendations(candidates)
        assert "bi_query" in text
        assert "推荐技能" in text


class TestSkillMdTriggers:
    def test_bi_analytics_frontmatter_loaded(self):
        from tars.skills.skill_md_parser import parse_skill_md

        path = SKILLS_DIR / "_global" / "bi_analytics" / "SKILL.md"
        smd = parse_skill_md(str(path))
        assert "查询数据" in smd.triggers
        assert "解释.*代码" in smd.skip_when
        assert smd.priority == 80


@pytest.mark.skill_eval
class TestSkillRoutingEval:
    def test_eval_hit_rate_and_false_triggers(self):
        if not os.getenv("SKILL_EVAL"):
            pytest.skip("Set SKILL_EVAL=1 to run routing eval")

        spec = _load_eval_cases()
        router, _ = _build_eval_router(use_embedding=False)
        extractor = IntentExtractor(use_embedding=False)

        positive = [c for c in spec["cases"] if c.get("expected_skill")]
        negative = [c for c in spec["cases"] if c.get("forbidden_skills")]

        hits = 0
        misses = []
        for case in positive:
            intent = extractor.extract(case["message"])
            ctx = case.get("context") or {}
            matched_ids = [c.skill_id for c in router.match(intent, context=ctx)]
            if case["expected_skill"] in matched_ids:
                hits += 1
            else:
                misses.append((case["message"], case["expected_skill"], matched_ids))

        hit_rate = hits / len(positive) if positive else 0.0
        min_hit = float(spec.get("min_hit_rate", 0.8))
        assert hit_rate >= min_hit, f"hit_rate={hit_rate:.2%}, misses={misses[:5]}"

        false_triggers = 0
        for case in negative:
            intent = extractor.extract(case["message"])
            ctx = case.get("context") or {}
            matched_ids = {c.skill_id for c in router.match(intent, context=ctx)}
            for forbidden in case.get("forbidden_skills") or []:
                if forbidden in matched_ids:
                    false_triggers += 1

        false_rate = false_triggers / len(negative) if negative else 0.0
        max_false = float(spec.get("max_false_trigger_rate", 0.05))
        assert false_rate <= max_false, f"false_trigger_rate={false_rate:.2%} > {max_false:.0%}"

    def test_eval_hit_rate_always(self):
        spec = _load_eval_cases()
        router, _ = _build_eval_router(use_embedding=False)
        extractor = IntentExtractor(use_embedding=False)

        positive = [c for c in spec["cases"] if c.get("expected_skill")]
        misses = []
        for case in positive:
            matched_ids = [
                c.skill_id for c in router.match(
                    extractor.extract(case["message"]),
                    context=case.get("context") or {},
                )
            ]
            if case["expected_skill"] not in matched_ids:
                misses.append((case["message"], case["expected_skill"], matched_ids))

        hit_rate = (len(positive) - len(misses)) / len(positive)
        assert hit_rate >= 0.80, f"hit_rate={hit_rate:.2%}, misses={misses}"
