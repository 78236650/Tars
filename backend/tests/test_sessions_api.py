"""Sessions API + Database 方法测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestDatabaseSessions:
    def test_list_sessions_returns_recent_first(self, tmp_path):
        from tars.database import Database
        import time
        db = Database(db_path=str(tmp_path / "t.db"))
        s1 = db.create_session(title="First")
        time.sleep(0.01)
        s2 = db.create_session(title="Second")
        time.sleep(0.01)
        s3 = db.create_session(title="Third")
        sessions = db.list_sessions()
        assert len(sessions) == 3
        assert sessions[0].id == s3.id
        assert sessions[2].id == s1.id

    def test_list_sessions_respects_limit(self, tmp_path):
        from tars.database import Database
        db = Database(db_path=str(tmp_path / "t.db"))
        for i in range(5):
            db.create_session(title=f"Session {i}")
        sessions = db.list_sessions(limit=3)
        assert len(sessions) == 3

    def test_delete_session_removes_messages(self, tmp_path):
        from tars.database import Database
        db = Database(db_path=str(tmp_path / "t.db"))
        s = db.create_session(title="To delete")
        db.add_message(s.id, "user", "hello")
        db.add_message(s.id, "assistant", "hi")
        assert len(db.get_messages(s.id)) == 2
        ok = db.delete_session(s.id)
        assert ok is True
        assert db.get_session(s.id) is None
        assert len(db.get_messages(s.id)) == 0

    def test_delete_nonexistent_session(self, tmp_path):
        from tars.database import Database
        db = Database(db_path=str(tmp_path / "t.db"))
        ok = db.delete_session("nonexistent-id")
        assert ok is False

    def test_update_session_title(self, tmp_path):
        from tars.database import Database
        db = Database(db_path=str(tmp_path / "t.db"))
        s = db.create_session(title="Old Title")
        ok = db.update_session_title(s.id, "New Title")
        assert ok is True
        updated = db.get_session(s.id)
        assert updated.title == "New Title"


class TestSessionsAPI:
    @pytest.fixture
    def client(self, tmp_path):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from tars.database import Database
        from tars.api.sessions import router, init_sessions_api
        app = FastAPI()
        app.include_router(router)
        db = Database(db_path=str(tmp_path / "t.db"))
        init_sessions_api(db)
        return TestClient(app)

    def test_create_session(self, client):
        resp = client.post("/api/sessions/")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["title"] == "New Chat"

    def test_list_sessions(self, client):
        client.post("/api/sessions/")
        client.post("/api/sessions/")
        resp = client.get("/api/sessions/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_messages_empty(self, client):
        s = client.post("/api/sessions/").json()
        resp = client.get(f"/api/sessions/{s['id']}/messages")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_messages_nonexistent(self, client):
        resp = client.get("/api/sessions/nonexistent/messages")
        assert resp.status_code == 404

    def test_delete_session(self, client):
        s = client.post("/api/sessions/").json()
        resp = client.delete(f"/api/sessions/{s['id']}")
        assert resp.status_code == 200
        listing = client.get("/api/sessions/").json()
        assert all(item["id"] != s["id"] for item in listing)

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/sessions/nonexistent")
        assert resp.status_code == 404

    def test_update_title(self, client):
        s = client.post("/api/sessions/").json()
        resp = client.patch(f"/api/sessions/{s['id']}", json={"title": "FastAPI 项目"})
        assert resp.status_code == 200
        listing = client.get("/api/sessions/").json()
        target = next(x for x in listing if x["id"] == s["id"])
        assert target["title"] == "FastAPI 项目"


class TestEndToEnd:
    def test_full_lifecycle(self, tmp_path):
        """创建会话 → 加消息 → 列出 → 更新标题 → 删除"""
        from tars.database import Database
        db = Database(db_path=str(tmp_path / "t.db"))

        s = db.create_session(title="Test")
        assert s.id

        db.add_message(s.id, "user", "Hello")
        db.add_message(s.id, "assistant", "Hi!")
        msgs = db.get_messages(s.id)
        assert len(msgs) == 2

        db.update_session_title(s.id, "Hello topic")
        assert db.get_session(s.id).title == "Hello topic"

        sessions = db.list_sessions()
        assert any(x.id == s.id for x in sessions)

        db.delete_session(s.id)
        assert db.get_session(s.id) is None
        assert len(db.get_messages(s.id)) == 0
