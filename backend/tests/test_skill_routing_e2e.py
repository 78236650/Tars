"""L2 — Skill routing integration (M1 + deploy intent)."""
from pathlib import Path

from tars.config.skills import SkillsConfig
from tars.memory.embeddings import DeterministicEmbeddingProvider
from tars.skills.intent_extractor import IntentExtractor
from tars.skills.loader import SkillLoader
from tars.skills.registry import SkillRegistry
from tars.skills.router import SkillRouter
from tars.tools.registry import ToolRegistry

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"


def _build_router():
    reg = SkillRegistry()
    loader = SkillLoader(
        skills_dir=str(SKILLS_DIR),
        tool_registry=ToolRegistry(),
        skill_registry=reg,
    )
    loader.invalidate_cache()
    loader._cache_valid = lambda _: False
    loader.load_all()
    cfg = SkillsConfig({
        "router": {
            "enabled": True,
            "top_k": 3,
            "min_score": 0.25,
            "use_embedding": False,
        }
    })
    return SkillRouter(reg, cfg, DeterministicEmbeddingProvider()), reg


class TestSkillRoutingE2E:
    def test_deploy_intent_routes_to_deploy_skill(self):
        router, _reg = _build_router()
        intent = IntentExtractor(use_embedding=False).extract("帮我部署服务到生产环境")
        matched = router.match(intent, {})
        ids = [c.skill_id for c in matched]
        assert "deploy" in ids

    def test_route_from_content_injects_deploy(self):
        router, _reg = _build_router()
        ranked = router.route_from_content("帮我把服务 deploy 到 production")
        assert ranked
        assert ranked[0][0].id == "deploy"

    def test_recommendations_for_data_query(self):
        router, _reg = _build_router()
        intent = IntentExtractor(use_embedding=False).extract("查询数据，看一下 GMV 趋势")
        candidates = router.match(intent, {})
        assert len(candidates) >= 1
