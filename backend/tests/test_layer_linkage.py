"""Four-module datasource_id linkage smoke test."""
import pytest


class TestDatasourceLinkage:
    def test_modules_share_spine_import(self):
        from tars.data.spine import fetch_rows
        from tars.report.service import ReportService
        from tars.governance.datasource_adapter import fetch_rows as gov_fetch
        assert fetch_rows is gov_fetch
        assert ReportService is not None

    def test_semantic_and_governance_registered_in_registry(self):
        from tars.modules.registry import ModuleRegistry
        reg = ModuleRegistry()
        reg.load()
        assert reg.get_layer("governance") == 2
        assert reg.get_layer("semantic") == 2
        assert reg.get_layer("meeting") == 1

    def test_insight_depends_on_bi_not_knowledge(self):
        from tars.modules.registry import ModuleRegistry
        reg = ModuleRegistry()
        reg.load()
        assert "bi" in reg.get_requires("insight")
        ok, _ = reg.check_dependencies("insight")
        assert ok is True
