"""Tests for semantic layer module."""
import pytest


@pytest.fixture
def semantic_service(tmp_path, monkeypatch):
    from tars.database import Database
    from tars.semantic.repository import SemanticRepository
    from tars.semantic.service import SemanticService

    db_path = tmp_path / "semantic_test.db"
    monkeypatch.setenv("TARS_DB_PATH", str(db_path))
    db = Database()
    repo = SemanticRepository(db)
    return SemanticService(repo)


class TestSemanticService:
    def test_seed_glossary(self, semantic_service):
        count = semantic_service.seed_glossary_if_empty(user_id="u1")
        assert count >= 30
        assert semantic_service.seed_glossary_if_empty(user_id="u1") == 0

    def test_lookup_for_question(self, semantic_service):
        semantic_service.seed_glossary_if_empty(user_id="u1")
        hits = semantic_service.lookup_for_question("今日 TEU 吞吐量多少", user_id="u1")
        terms = {h.term for h in hits}
        assert "TEU" in terms or "吞吐量" in terms

    def test_suggest_from_columns(self, semantic_service):
        semantic_service.seed_glossary_if_empty(user_id="u1")
        created = semantic_service.suggest_from_columns(
            "ds-1", "vessel_calls", ["teu_count", "berth_name"], user_id="u1",
        )
        assert len(created) >= 1

    def test_create_and_list_terms(self, semantic_service):
        t = semantic_service.create_term(
            term="测试术语", definition="测试定义", user_id="u1",
        )
        terms = semantic_service.list_terms(user_id="u1")
        assert any(x.id == t.id for x in terms)
