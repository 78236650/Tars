"""治理 API 端到端：建数据源 → 建规则 → 跑校验 → QualityReport。"""
import sqlite3
import pytest
from fastapi.testclient import TestClient

from tars.main import app
from tars.database.bi_store import init_bi_store
from tests.conftest import setup_admin_auth


@pytest.fixture
def api_ctx(tmp_path, test_db):
    """建外部数据源 + admin 认证头。"""
    dbfile = tmp_path / "ext.db"
    c = sqlite3.connect(dbfile)
    c.execute("CREATE TABLE items (id INTEGER, name TEXT)")
    c.executemany("INSERT INTO items VALUES (?, ?)", [(1, "a"), (2, None), (3, "c")])
    c.commit()
    c.close()
    store = init_bi_store(test_db)
    ds = store.create(tenant_id="org_default", name="ext", db_type="sqlite",
                      connection_url=f"sqlite:///{dbfile}")
    headers, _user = setup_admin_auth(test_db)
    return TestClient(app), headers, ds.id, test_db


def test_full_flow(api_ctx):
    client, headers, ds_id, test_db = api_ctx

    # 1. 建规则：name 非空
    r = client.post("/api/governance/rules", headers=headers, json={
        "datasource_id": ds_id, "table_name": "items", "kind": "not_null",
        "name": "名称非空", "params": {"field": "name"},
    })
    assert r.status_code == 200, r.text
    rule = r.json()
    assert rule["kind"] == "not_null"
    rule_id = rule["id"]

    # 2. 列规则列表
    r = client.get("/api/governance/rules", headers=headers,
                   params={"datasource_id": ds_id, "table_name": "items"})
    assert r.status_code == 200
    assert len(r.json()["rules"]) == 1

    # 3. 跑校验
    r = client.post("/api/governance/validate", headers=headers,
                    params={"datasource_id": ds_id, "table_name": "items"})
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["status"] == "failed"  # 有一行 name=None
    assert report["total_rows"] == 3
    assert report["truncated"] is False
    summary = report["summary"]
    assert summary["rule_results"][0]["failed_count"] == 1
    assert len(summary["rule_results"][0]["sample_violations"]) == 1

    # 4. 删除规则
    r = client.delete(f"/api/governance/rules/{rule_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["deleted"] == rule_id
