"""Tests for Layer2 DataSpine."""
import pytest


class TestDataSpine:
    def test_fetch_rows_table_sql_mutually_exclusive(self):
        from tars.data.spine import fetch_rows
        with pytest.raises(ValueError, match="二选一"):
            fetch_rows("ds-1")
        with pytest.raises(ValueError, match="二选一"):
            fetch_rows("ds-1", table="t", sql="SELECT 1")

    def test_governance_adapter_reexports_spine(self):
        from tars.governance.datasource_adapter import fetch_rows as gov_fetch
        from tars.data.spine import fetch_rows as spine_fetch
        assert gov_fetch is spine_fetch

    def test_result_set_shared_model(self):
        from tars.data.models import ResultSet
        from tars.governance.result_set import ResultSet as GovRS
        assert ResultSet is GovRS
