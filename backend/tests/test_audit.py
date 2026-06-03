"""Tests for TARS audit logger — Phase 1 Task 3."""
import pytest
from tars.database.base import Database, AuditLog


class TestAuditLogger:
    """Verify AuditLogger writes and retrieves audit entries correctly."""

    def test_log_tool_call(self, db_with_audit):
        db, logger = db_with_audit
        logger.log_tool_call(
            tool_name="shell",
            tenant_id="t1",
            user_id="u1",
            arguments={"cmd": "ls"},
            success=True,
        )
        logs, total = logger.list(tenant_id="t1")
        assert total == 1
        assert logs[0].action == "tool_call:success"
        assert logs[0].resource_id == "shell"

    def test_log_permission_denied(self, db_with_audit):
        db, logger = db_with_audit
        logger.log_permission_denied(
            resource="shell",
            resource_type="tool",
            tenant_id="t1",
            user_id="u1",
            reason="guest 无权使用 shell",
        )
        logs, total = logger.list(tenant_id="t1")
        assert total == 1
        assert logs[0].action == "permission_denied"

    def test_log_memory_access(self, db_with_audit):
        db, logger = db_with_audit
        logger.log_memory_access(
            memory_id="mem-001",
            action="read",
            tenant_id="t1",
            user_id="u1",
        )
        logs, _ = logger.list(tenant_id="t1")
        assert logs[0].action == "memory:read"
        assert logs[0].resource_id == "mem-001"

    def test_log_model_call(self, db_with_audit):
        db, logger = db_with_audit
        logger.log_model_call(
            model_name="qwen-max",
            tenant_id="t1",
            user_id="u1",
            token_count=3500,
        )
        logs, _ = logger.list(tenant_id="t1")
        assert logs[0].action == "model_call"
        assert "3500" in logs[0].detail

    def test_multiple_entries_ordered(self, db_with_audit):
        db, logger = db_with_audit
        import time
        logger.log_tool_call("tool_a", tenant_id="t1", user_id="u1")
        time.sleep(0.1)
        logger.log_tool_call("tool_b", tenant_id="t1", user_id="u1")
        logs, total = logger.list(tenant_id="t1")
        assert total == 2
        # newest first
        assert logs[0].resource_id == "tool_b"
        assert logs[1].resource_id == "tool_a"

    def test_tenant_isolation(self, db_with_audit):
        db, logger = db_with_audit
        logger.log_tool_call("weather", tenant_id="t1", user_id="u1")
        logger.log_tool_call("shell", tenant_id="t2", user_id="u2")
        t1_logs, t1_total = logger.list(tenant_id="t1")
        t2_logs, t2_total = logger.list(tenant_id="t2")
        assert t1_total == 1
        assert t2_total == 1
        assert t1_logs[0].resource_id == "weather"
        assert t2_logs[0].resource_id == "shell"

    def test_list_all_tenants_when_unfiltered(self, db_with_audit):
        db, logger = db_with_audit
        logger.log_tool_call("weather", tenant_id="t1", user_id="u1")
        logger.log_tool_call("shell", tenant_id="t2", user_id="u2")
        logs, total = logger.list()
        assert total == 2
        assert {log.resource_id for log in logs} == {"weather", "shell"}

    def test_pagination(self, db_with_audit):
        db, logger = db_with_audit
        for i in range(5):
            logger.log_tool_call(f"tool_{i}", tenant_id="t1", user_id="u1")
        page1, total = logger.list(tenant_id="t1", page=1, page_size=3)
        page2, _ = logger.list(tenant_id="t1", page=2, page_size=3)
        assert total == 5
        assert len(page1) == 3
        assert len(page2) == 2

    def test_non_blocking_on_db_error(self, tmp_path):
        """AuditLogger should not raise even if DB is closed after init."""
        from tars.security.audit import AuditLogger
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        logger = AuditLogger(db)
        db.close()
        # Should not raise (try/except catches the error)
        logger.log_tool_call("test", "t1", "u1")

    def test_log_login_and_user_event(self, db_with_audit):
        db, logger = db_with_audit
        logger.log_login(user_id="u1", tenant_id="u1", success=True, detail="admin")
        logger.log_user_event("user_create", "u2", actor_id="u1", tenant_id="u1")
        logs, total = logger.list()
        assert total == 2
        actions = {log.action for log in logs}
        assert "login" in actions
        assert "user_create" in actions


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def db_with_audit(tmp_path):
    from tars.security.audit import AuditLogger
    db_path = tmp_path / "test_audit.db"
    db = Database(str(db_path))
    logger = AuditLogger(db)
    yield db, logger
    db.close()


@pytest.fixture
def audit_client(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from tars.api.audit import router as audit_router, init_audit_api

    from tests.conftest import setup_admin_auth, setup_main_api_auth

    db = Database(str(tmp_path / "audit_api.db"))
    init_audit_api(db)
    admin_headers, _admin = setup_admin_auth(db)
    user_headers, _user = setup_main_api_auth(db)
    app = FastAPI()
    app.include_router(audit_router)
    return TestClient(app), db, admin_headers, user_headers


class TestAuditApi:
    def test_admin_can_list_all_tenants(self, audit_client):
        client, db, admin_headers, _user_headers = audit_client
        db.add_audit_log("permission_denied", "tool", tenant_id="user-a", user_id="u1", resource_id="shell")
        db.add_audit_log("permission_denied", "tool", tenant_id="user-b", user_id="u2", resource_id="weather")

        resp = client.get("/api/audit/logs", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["timestamp"]
        assert data["items"][0]["resource"] == "tool:weather"
        assert data["items"][0]["ip_address"] == ""

    def test_non_admin_forbidden(self, audit_client):
        client, _, _admin_headers, user_headers = audit_client
        resp = client.get("/api/audit/logs", headers=user_headers)
        assert resp.status_code == 403

    def test_filter_by_tenant_id(self, audit_client):
        client, db, admin_headers, _user_headers = audit_client
        db.add_audit_log("tool_call:success", "tool", tenant_id="tenant-a", user_id="u1", resource_id="a")
        db.add_audit_log("tool_call:success", "tool", tenant_id="tenant-b", user_id="u2", resource_id="b")

        resp = client.get(
            "/api/audit/logs",
            headers=admin_headers,
            params={"tenant_id": "tenant-a"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["resource_id"] == "a"
