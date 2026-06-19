"""治理 module health 路由接入测试。"""
from fastapi.testclient import TestClient

from tars.main import app
from tests.conftest import setup_admin_auth


def test_health_returns_ok(test_db):
    headers, _user = setup_admin_auth(test_db)
    client = TestClient(app)
    resp = client.get("/api/governance/health", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["module"] == "governance"
