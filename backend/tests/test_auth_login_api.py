import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))


def _build_store(tmp_path, monkeypatch, db_name="auth.db"):
    from tars.database import Database, UserStore
    from tars.database.auth_token_store import AuthTokenStore
    import tars.main as main

    test_db = Database(db_path=str(tmp_path / db_name))
    test_store = UserStore(test_db)
    test_tokens = AuthTokenStore(test_db)
    from tars.api._auth import init_auth

    monkeypatch.setattr(main, "user_store", test_store)
    monkeypatch.setattr(main, "auth_token_store", test_tokens)
    init_auth(test_store, test_tokens)
    monkeypatch.setenv("TARS_JWT_SECRET", "test-jwt-secret-for-login-api-tests")
    return main, test_db, test_store


@pytest.fixture
def client(tmp_path, monkeypatch):
    main, test_db, test_store = _build_store(tmp_path, monkeypatch)

    with TestClient(main.app) as test_client:
        yield test_client, test_store

    test_db.close()


def test_get_all_users_includes_role_template_id(client):
    from tars.gateway.permission import UserRole

    http, store = client
    user = store.create_user(
        username="dev",
        email="dev@example.com",
        role=UserRole.USER,
        password="DevPass123!",
    )
    store.update_user(user.id, role_template_id="developer")

    listed = store.get_all_users()
    match = next(u for u in listed if u.id == user.id)
    assert match.role_template_id == "developer"

    response = http.get("/api/users")
    assert response.status_code == 200
    payload = response.json()["users"]
    api_user = next(u for u in payload if u["id"] == user.id)
    assert api_user["role_template_id"] == "developer"


def test_create_user_requires_password(client):
    http, store = client
    admin = store.create_user(
        username="creator",
        email="creator@example.com",
        password="CreatorPass1!",
    )

    response = http.post(
        "/api/users",
        json={"username": "bob", "email": "bob@example.com", "role": "user"},
        headers={"X-API-Key": admin.api_key},
    )

    assert response.status_code == 422


def test_create_user_rejects_short_password(client):
    http, store = client
    admin = store.create_user(
        username="creator2",
        email="creator2@example.com",
        password="CreatorPass1!",
    )

    response = http.post(
        "/api/users",
        json={
            "username": "bob",
            "email": "bob2@example.com",
            "password": "short7!",
            "role": "user",
        },
        headers={"X-API-Key": admin.api_key},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "初始密码至少 8 位"


def test_login_returns_existing_api_key_and_updates_last_login(client):
    http, store = client
    test_user = store.create_user(
        username="admin",
        email="admin@example.com",
        password="Adm1nPass!",
    )

    response = http.post(
        "/api/auth/login",
        json={"identifier": "admin@example.com", "password": "Adm1nPass!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["api_key"] == test_user.api_key
    assert data["data"]["user"]["username"] == "admin"
    assert data["data"]["user"]["last_login"] is not None
    assert store.get_user_by_id(test_user.id).last_login is not None


def test_login_rejects_invalid_credentials(client):
    http, store = client
    store.create_user(
        username="admin",
        email="admin@example.com",
        password="Adm1nPass!",
    )

    response = http.post(
        "/api/auth/login",
        json={"identifier": "admin@example.com", "password": "wrong-pass"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "用户名或密码错误"


def test_startup_bootstraps_default_admin_and_allows_login(client):
    http, store = client

    bootstrapped_user = store.get_user_by_email("admin@tars.local")

    assert bootstrapped_user is not None
    assert bootstrapped_user.username == "admin"
    assert bootstrapped_user.role.value == "admin"

    response = http.post(
        "/api/auth/login",
        json={"identifier": "admin@tars.local", "password": "Admin123!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["user"]["email"] == "admin@tars.local"
    assert data["data"]["user"]["role"] == "admin"


def test_ensure_default_admin_does_not_create_duplicate_admin_when_admin_exists(
    tmp_path, monkeypatch
):
    from tars.gateway.permission import UserRole

    main, test_db, store = _build_store(tmp_path, monkeypatch, db_name="existing-admin.db")
    try:
        existing_admin = store.create_user(
            username="root",
            email="root@example.com",
            role=UserRole.ADMIN,
            password="RootPass123!",
        )

        created_user = main.ensure_default_admin()

        admins = [user for user in store.get_all_users() if user.role == UserRole.ADMIN]
        assert created_user is None
        assert len(admins) == 1
        assert admins[0].id == existing_admin.id
        assert store.get_user_by_email("admin@tars.local") is None
    finally:
        test_db.close()


def test_ensure_default_admin_skips_when_default_identity_is_taken_by_non_admin(
    tmp_path, monkeypatch
):
    from tars.gateway.permission import UserRole

    main, test_db, store = _build_store(tmp_path, monkeypatch, db_name="conflict-user.db")
    try:
        store.create_user(
            username="worker",
            email="admin@tars.local",
            role=UserRole.USER,
            password="WorkerPass123!",
        )

        created_user = main.ensure_default_admin()

        users = store.get_all_users()
        assert created_user is None
        assert len(users) == 1
        assert users[0].role == UserRole.USER
        assert users[0].email == "admin@tars.local"
    finally:
        test_db.close()


def test_ensure_default_admin_backfills_admin_when_only_regular_users_exist(
    tmp_path, monkeypatch
):
    from tars.gateway.permission import UserRole

    main, test_db, store = _build_store(tmp_path, monkeypatch, db_name="backfill-admin.db")
    try:
        existing_user = store.create_user(
            username="alice",
            email="alice@example.com",
            role=UserRole.USER,
            password="AlicePass123!",
        )

        created_user = main.ensure_default_admin()

        users = store.get_all_users()
        admins = [user for user in users if user.role == UserRole.ADMIN]
        assert created_user is not None
        assert created_user.role == UserRole.ADMIN
        assert created_user.username == "admin"
        assert created_user.email == "admin@tars.local"
        assert len(users) == 2
        assert len(admins) == 1
        assert store.get_user_by_email(existing_user.email).role == UserRole.USER
    finally:
        test_db.close()
