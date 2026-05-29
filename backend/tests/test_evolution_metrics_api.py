"""Task 11: Evolution metrics API 测试。"""

from fastapi.testclient import TestClient
from tars.main import app


def test_evolution_metrics_endpoint():
    client = TestClient(app)
    r = client.get("/api/evolution/metrics?tenant_id=default")
    assert r.status_code == 200
    body = r.json()
    assert "stats" in body and "recent_feedback" in body
