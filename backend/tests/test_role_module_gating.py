"""Phase 1: role module gating for business_analyst vs analyst."""
import pytest
from tars.database import Database
from tars.gateway.role_template import RoleTemplateManager


@pytest.fixture
def manager(tmp_path):
    db = Database(db_path=str(tmp_path / "test.db"))
    return RoleTemplateManager(db)


class TestBusinessAnalystRole:
    def test_business_analyst_seeded(self, manager):
        t = manager.get_template("business_analyst")
        assert t is not None
        assert t.name == "业务分析师"

    def test_business_analyst_has_insight_not_bi(self, manager):
        t = manager.get_template("business_analyst")
        assert "insight" in t.allowed_modules
        assert "bi" not in t.allowed_modules

    def test_insight_analyst_has_no_bi(self, manager):
        t = manager.get_template("insight_analyst")
        assert "insight" in t.allowed_modules
        assert "bi" not in t.allowed_modules

    def test_analyst_has_bi_and_insight(self, manager):
        t = manager.get_template("analyst")
        assert "bi" in t.allowed_modules
        assert "insight" in t.allowed_modules

    def test_standard_has_bi_and_insight(self, manager):
        t = manager.get_template("standard")
        assert "insight" in t.allowed_modules
        assert "bi" in t.allowed_modules
