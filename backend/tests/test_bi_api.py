"""BI REST API integration tests — datasource CRUD, query, role gating."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import uuid

import pytest
from fastapi.testclient import TestClient

from tars.database import Database
from tars.database.user_store import UserRole


@pytest.fixture
def sample_sqlite_url():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, gmv REAL)")
    conn.execute("INSERT INTO orders VALUES (1, 100.0)")
    conn.commit()
    conn.close()
    url = f"sqlite:///{tmp.name}"
    yield url
    os.unlink(tmp.name)


@pytest.fixture
def bi_client():
    from tars.main import app, user_store

    admin = None
    for u in user_store.get_all_users():
        if u.role == UserRole.ADMIN:
            admin = u
            break
    if not admin:
        name = f"bi_admin_{uuid.uuid4().hex[:6]}"
        admin = user_store.create_user(
            username=name,
            email=f"{name}@test.local",
            role=UserRole.ADMIN,
        )

    client = TestClient(app)
    headers = {"X-API-Key": admin.api_key}
    return client, headers, admin


def test_bi_module_listed(bi_client):
    client, _, _ = bi_client
    res = client.get("/api/modules")
    assert res.status_code == 200
    bi_mod = next((m for m in res.json() if m["name"] == "bi"), None)
    assert bi_mod is not None
    assert bi_mod["enabled"] is True


def test_create_list_query_datasource(bi_client, sample_sqlite_url):
    client, headers, admin = bi_client

    create_res = client.post(
        "/api/datasources/",
        headers=headers,
        json={
            "name": "api-test-sqlite",
            "db_type": "sqlite",
            "connection_url": sample_sqlite_url,
        },
    )
    assert create_res.status_code == 200, create_res.text
    body = create_res.json()
    assert body["success"] is True
    ds_id = body["datasource"]["id"]
    assert body["datasource"]["schema_snapshot"]["tables"]["orders"]

    list_res = client.get("/api/datasources/", headers=headers)
    assert list_res.status_code == 200
    ids = [d["id"] for d in list_res.json()["datasources"]]
    assert ds_id in ids

    query_res = client.post(
        f"/api/datasources/{ds_id}/query",
        headers=headers,
        json={"sql": "SELECT COUNT(*) AS cnt FROM orders"},
    )
    assert query_res.status_code == 200, query_res.text
    q = query_res.json()
    assert q["success"] is True
    assert q["data"][0]["cnt"] == 1

    chart_res = client.post(
        f"/api/datasources/{ds_id}/chart",
        headers=headers,
        json={"sql": "SELECT id, gmv FROM orders", "user_question": "订单 GMV"},
    )
    assert chart_res.status_code == 200, chart_res.text
    chart = chart_res.json()
    assert "chart_type" in chart
    assert "echarts_option" in chart

    delete_res = client.delete(f"/api/datasources/{ds_id}", headers=headers)
    assert delete_res.status_code == 200


def test_standard_role_can_access_bi_api(bi_client, sample_sqlite_url):
    from tars.main import user_store

    client, _, _ = bi_client
    name = f"std_bi_{uuid.uuid4().hex[:6]}"
    user = user_store.create_user(username=name, email=f"{name}@t.local", role=UserRole.USER)
    user_store.update_user(user.id, role_template_id="standard")
    user = user_store.get_user_by_id(user.id)
    headers = {"X-API-Key": user.api_key}

    list_res = client.get("/api/datasources/", headers=headers)
    assert list_res.status_code == 200, list_res.text

    create_res = client.post(
        "/api/datasources/",
        headers=headers,
        json={
            "name": "std-user-ds",
            "db_type": "sqlite",
            "connection_url": sample_sqlite_url,
        },
    )
    assert create_res.status_code == 200, create_res.text
    ds_id = create_res.json()["datasource"]["id"]
    client.delete(f"/api/datasources/{ds_id}", headers=headers)


def test_business_analyst_role_cannot_access_bi_api(bi_client):
    from tars.main import user_store

    client, _, _ = bi_client
    name = f"biz_{uuid.uuid4().hex[:6]}"
    user = user_store.create_user(username=name, email=f"{name}@t.local", role=UserRole.USER)
    user_store.update_user(user.id, role_template_id="business_analyst")
    user = user_store.get_user_by_id(user.id)
    headers = {"X-API-Key": user.api_key}

    res = client.get("/api/datasources/", headers=headers)
    assert res.status_code == 403


def test_bi_store_singleton_shared_with_api(bi_client, sample_sqlite_url):
    from tars.api import bi as bi_api
    from tars.database.bi_store import get_bi_store

    client, headers, admin = bi_client
    create_res = client.post(
        "/api/datasources/",
        headers=headers,
        json={
            "name": "shared-store-ds",
            "db_type": "sqlite",
            "connection_url": sample_sqlite_url,
        },
    )
    assert create_res.status_code == 200
    ds_id = create_res.json()["datasource"]["id"]

    assert bi_api._store is get_bi_store()
    listed = get_bi_store().list_by_tenant(admin.id)
    assert any(ds.id == ds_id for ds in listed)

    client.delete(f"/api/datasources/{ds_id}", headers=headers)


def test_create_with_structured_fields(bi_client, sample_sqlite_url):
    client, headers, _ = bi_client
    db_path = sample_sqlite_url.replace("sqlite:///", "")

    create_res = client.post(
        "/api/datasources/",
        headers=headers,
        json={
            "name": "structured-sqlite",
            "db_type": "sqlite",
            "database": db_path,
        },
    )
    assert create_res.status_code == 200, create_res.text
    body = create_res.json()
    ds_id = body["datasource"]["id"]
    conn = body["datasource"].get("connection") or {}
    assert conn.get("database") == db_path
    assert "password" not in conn

    test_res = client.post(
        "/api/datasources/test-config",
        headers=headers,
        json={"db_type": "sqlite", "database": db_path},
    )
    assert test_res.status_code == 200, test_res.text
    assert test_res.json()["success"] is True

    client.delete(f"/api/datasources/{ds_id}", headers=headers)
