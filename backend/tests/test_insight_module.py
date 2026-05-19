"""InsightForge module scaffold tests (INS-1.0.0)."""
import pytest
from fastapi.testclient import TestClient

from tars.database import Database
from tars.insight.config import get_insight_config, load_insight_config
from tars.insight.store import InsightProfileRunStore
from tars.insight.version import CAPABILITY_NAME, INS_VERSION
from tars.modules.registry import ModuleRegistry


def test_insight_version_constants():
    assert CAPABILITY_NAME == "insight-forge"
    assert INS_VERSION == "INS-1.0.0"


def test_insight_config_tier1_includes_doris():
    cfg = load_insight_config()
    assert "doris" in cfg.tier1_databases
    assert cfg.profile_mode_for_db("doris") == "full"
    assert cfg.stats_dialect_key("doris") == "mysql"


def test_module_registry_insight_requires():
    reg = ModuleRegistry()
    reg.load()
    if reg.is_enabled("insight"):
        assert "bi" in reg.get_requires("insight")
        assert "knowledge" in reg.get_requires("insight")


def test_profile_run_store_crud():
    db = Database(":memory:")
    store = InsightProfileRunStore(db)
    run = store.create(
        datasource_id="ds-1",
        tenant_id="default",
        capability_version=INS_VERSION,
        budget={"max_tables": 10},
    )
    assert run is not None
    assert run.status == "pending"
    loaded = store.get(run.id, "default")
    assert loaded is not None
    assert loaded.datasource_id == "ds-1"


@pytest.fixture
def insight_client():
    from tars.main import app

    return TestClient(app)


def test_insight_version_endpoint(insight_client):
    res = insight_client.get("/api/insight/version")
    if res.status_code == 503:
        pytest.skip("insight module disabled in modules.yaml")
    assert res.status_code == 200
    data = res.json()
    assert data["capability"] == "insight-forge"
    assert data["version"] == "INS-1.0.0"
    assert "doris" in data["tier1_databases"]


def test_insight_brief_endpoint_shape(insight_client):
    """GET /api/insight/datasources/{id}/brief returns workbench payload."""
    res = insight_client.get("/api/insight/version")
    if res.status_code == 503:
        pytest.skip("insight module disabled in modules.yaml")

    # 使用 admin 租户（与常见本地库一致）
    tenant = "4a863625-6bc1-472d-8ce1-c83511c95e49"
    ds_res = insight_client.get(
        "/api/datasources/",
        headers={"X-Tenant-ID": tenant},
    )
    if ds_res.status_code != 200:
        pytest.skip("no datasources")
    dss = ds_res.json().get("datasources") or []
    if not dss:
        pytest.skip("no datasources")

    ds_id = dss[0]["id"]
    brief_res = insight_client.get(
        f"/api/insight/datasources/{ds_id}/brief",
        headers={"X-Tenant-ID": tenant},
    )
    assert brief_res.status_code == 200, brief_res.text
    body = brief_res.json()
    assert "datasource" in body
    assert "schema_annotations" in body
    assert "insight_snapshot" in body
    assert body["phase"]["workbench"] is True


def test_schema_explorer_supports_doris():
    from tars.bi.schema_explorer import SchemaExplorer

    assert "doris" in SchemaExplorer.SUPPORTED_TYPES
