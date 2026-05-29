"""Task 8: 应用启动 smoke test。"""

from fastapi.testclient import TestClient
from tars.main import app


def test_app_has_routes():
    """确认 FastAPI app 可启动且包含 /api 路由。"""
    client = TestClient(app)
    paths = {r.path for r in app.routes}
    assert any(p.startswith("/api") for p in paths)
