"""报表后端测试 — chartspec + aggregate + API。"""
import sqlite3
import pytest
from fastapi.testclient import TestClient

from tars.main import app
from tars.database.bi_store import init_bi_store
from tests.conftest import setup_admin_auth
from tars.report.chartspec import ChartSpec, validate_spec, DimensionSpec, MeasureSpec
from tars.report.aggregate import aggregate
from tars.report.renderer import render


# ── chartspec tests ─────────────────────────────────────────

def test_chart_spec_from_dict():
    spec = ChartSpec.from_dict({
        "chart_type": "bar",
        "dimensions": [{"field": "category"}],
        "measures": [{"field": "amount", "agg": "sum"}],
    })
    assert spec.chart_type == "bar"
    assert len(spec.dimensions) == 1
    assert spec.measures[0].agg == "sum"


def test_validate_spec_valid():
    errors = validate_spec(
        ChartSpec.from_dict({"chart_type": "pie", "dimensions": [{"field": "x"}], "measures": [{"field": "y", "agg": "count"}]}),
        ["x", "y"], {},
    )
    assert len(errors) == 0


def test_validate_spec_missing_field():
    errors = validate_spec(
        ChartSpec.from_dict({"chart_type": "bar", "dimensions": [{"field": "z"}], "measures": [{"field": "y", "agg": "sum"}]}),
        ["x", "y"], {},
    )
    assert any("z" in e for e in errors)


# ── aggregate tests ────────────────────────────────────────

def test_aggregate_sum():
    spec = ChartSpec.from_dict({"chart_type": "bar", "dimensions": [{"field": "cat"}], "measures": [{"field": "val", "agg": "sum"}]})
    result = aggregate(
        [["a", 10], ["a", 20], ["b", 5]],
        ["cat", "val"], spec,
    )
    assert result.rows == [["a", 30], ["b", 5]]


# ── API test ────────────────────────────────────────────────

@pytest.fixture
def api_ctx(tmp_path, test_db):
    dbfile = tmp_path / "sales.db"
    c = sqlite3.connect(dbfile)
    c.execute("CREATE TABLE sales (category TEXT, amount REAL)")
    c.executemany("INSERT INTO sales VALUES (?, ?)", [("A", 100), ("A", 200), ("B", 50)])
    c.commit(); c.close()
    store = init_bi_store(test_db)
    ds = store.create(tenant_id="org_default", name="sales", db_type="sqlite",
                      connection_url=f"sqlite:///{dbfile}")
    headers, _user = setup_admin_auth(test_db)
    return TestClient(app), headers, ds.id


def test_report_execute_chart(api_ctx):
    client, headers, ds_id = api_ctx
    r = client.post("/api/report/charts/execute", headers=headers, json={
        "datasource_id": ds_id, "table_name": "sales",
        "spec": {"chart_type": "bar", "dimensions": [{"field": "category"}],
                 "measures": [{"field": "amount", "agg": "sum"}]},
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["categories"] == ["A", "B"]
    assert len(data["series"]) == 1
    assert data["series"][0]["data"] == [300, 50]
