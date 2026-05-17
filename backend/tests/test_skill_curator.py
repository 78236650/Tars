"""Tests for Skills Curator — v4.0.0 Phase 4 Task 7."""
import pytest
from tars.database import Database


class TestSkillCurator:
    """Verify SkillCurator tracking + archive lifecycle."""

    def test_record_call(self, curator_db):
        db, curator = curator_db
        curator.record_call("calculator")
        stats = curator.get_stats()
        assert len(stats) == 1
        assert stats[0]["skill_id"] == "calculator"
        assert stats[0]["total_calls"] == 1
        assert stats[0]["state"] == "active"

    def test_multiple_calls(self, curator_db):
        db, curator = curator_db
        for _ in range(3):
            curator.record_call("translate")
        stats = curator.get_stats()
        assert stats[0]["total_calls"] == 3

    def test_archive(self, curator_db):
        db, curator = curator_db
        curator.record_call("web_search")
        curator.archive("web_search")
        stats = curator.get_stats()
        assert stats[0]["state"] == "archived"
        assert curator.is_archived("web_search") is True

    def test_activate(self, curator_db):
        db, curator = curator_db
        curator.record_call("weather")
        curator.archive("weather")
        assert curator.is_archived("weather") is True
        curator.activate("weather")
        assert curator.is_archived("weather") is False

    def test_get_single_skill_stats(self, curator_db):
        db, curator = curator_db
        curator.record_call("code")
        stats = curator.get_skill_stats("code")
        assert stats["skill_id"] == "code"
        assert stats["total_calls"] == 1

    def test_nonexistent_skill(self, curator_db):
        db, curator = curator_db
        stats = curator.get_skill_stats("nonexistent")
        assert stats is None

    def test_empty_stats(self, curator_db):
        db, curator = curator_db
        stats = curator.get_stats()
        assert stats == []

    def test_sort_by_calls(self, curator_db):
        db, curator = curator_db
        curator.record_call("low")
        curator.record_call("high")
        curator.record_call("high")
        curator.record_call("mid")
        stats = curator.get_stats()
        # Sorted by total_calls DESC
        assert stats[0]["skill_id"] == "high"
        assert stats[0]["total_calls"] == 2
        assert stats[1]["skill_id"] == "low"
        assert stats[2]["skill_id"] == "mid"


@pytest.fixture
def curator_db(tmp_path):
    from tars.skills.curator import SkillCurator
    db_path = tmp_path / "test_curator.db"
    db = Database(str(db_path))
    curator = SkillCurator(db)
    yield db, curator
    db.close()
