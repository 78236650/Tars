"""SkillOptimizer routing adoption integration."""
import tars.database.skill_routing_store as routing_mod
from tars.database import Database
from tars.database.skill_routing_store import SkillRoutingStore, init_skill_routing_store
from tars.evolution.skill_optimizer import SkillOptimizer
from tars.skills.router import SkillCandidate


def test_suggest_trigger_patches_for_low_adoption():
    db = Database(":memory:")
    store = SkillRoutingStore(db)
    store.ensure_schema()
    routing_mod._store_singleton = store

    for _ in range(12):
        store.record_recommendations(
            "sess-1",
            [SkillCandidate(skill_id="noisy-skill", score=0.9, match_reason="keyword")],
        )
    store.mark_adopted("sess-1", "noisy-skill")

    opt = SkillOptimizer(db, min_recommendations=10, low_adoption_rate=0.4)
    suggestions = opt.suggest_trigger_patches()
    assert len(suggestions) == 1
    assert suggestions[0]["skill_id"] == "noisy-skill"
    assert suggestions[0]["kind"] == "routing"
    assert suggestions[0]["adoption_rate"] < 0.4


def test_init_skill_routing_store_singleton():
    db = Database(":memory:")
    init_skill_routing_store(db)
    assert routing_mod.get_skill_routing_store() is not None
