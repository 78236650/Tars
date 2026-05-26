import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from tars.wiki.store import WikiStore
from tars.api.wiki import create_wiki_router


@pytest.fixture
def app(tmp_path):
    store = WikiStore(wiki_dir=tmp_path)
    store.write_page("port-ops", "# 港口运营\n\n内容")
    store.update_index({"port-ops": "港口运营相关知识"})
    app = FastAPI()
    app.include_router(create_wiki_router(store), prefix="/api/wiki")
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_list_pages(client):
    resp = client.get("/api/wiki/")
    assert resp.status_code == 200
    data = resp.json()
    assert "port-ops" in [p["name"] for p in data["pages"]]


def test_get_page(client):
    resp = client.get("/api/wiki/port-ops")
    assert resp.status_code == 200
    assert "港口运营" in resp.json()["content"]


def test_get_nonexistent_page(client):
    resp = client.get("/api/wiki/nonexistent")
    assert resp.status_code == 404


def test_update_page(client):
    resp = client.put("/api/wiki/port-ops", json={"content": "# 港口运营\n\n更新内容"})
    assert resp.status_code == 200
    resp2 = client.get("/api/wiki/port-ops")
    assert "更新内容" in resp2.json()["content"]


def test_delete_page(client):
    resp = client.delete("/api/wiki/port-ops")
    assert resp.status_code == 200
    resp2 = client.get("/api/wiki/port-ops")
    assert resp2.status_code == 404
