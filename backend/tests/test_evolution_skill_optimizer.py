"""SkillOptimizer tests."""
from tars.database import Database
from tars.evolution.skill_optimizer import SkillOptimizer


def test_suggest_patches_for_low_success_rate():
    db = Database(":memory:")
    conn = db._get_conn()
    conn.execute(
        """
        CREATE TABLE skill_usage (
            skill_id TEXT PRIMARY KEY,
            total_calls INTEGER NOT NULL DEFAULT 0,
            last_called REAL NOT NULL DEFAULT 0.0,
            state TEXT NOT NULL DEFAULT 'active',
            success_count INTEGER NOT NULL DEFAULT 0,
            fail_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        "INSERT INTO skill_usage VALUES (?, ?, ?, ?, ?, ?)",
        ("low-skill", 15, 0.0, "active", 2, 8),
    )
    conn.commit()

    opt = SkillOptimizer(db, min_calls=10, low_success_rate=0.4)
    suggestions = opt.suggest_patches()
    assert len(suggestions) == 1
    assert suggestions[0]["skill_id"] == "low-skill"
    assert suggestions[0]["success_rate"] < 0.4
