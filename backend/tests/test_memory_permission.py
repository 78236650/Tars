"""Tests for TARS memory permission — Phase 1 Task 6."""
import pytest
from tars.security.memory_permission import (
    MemoryPermission, MemoryScope, init_memory_permission,
)


class TestMemoryPermission:
    """Verify scope-based memory access control."""

    def test_same_tenant_can_read_private(self):
        mp = MemoryPermission()
        assert mp.can_read("private", "t1", "t1")

    def test_same_tenant_can_read_shared(self):
        mp = MemoryPermission()
        assert mp.can_read("shared", "t1", "t1")

    def test_same_tenant_can_write(self):
        mp = MemoryPermission()
        assert mp.can_write("private", "t1", "t1")

    def test_cross_tenant_cannot_read_private(self):
        mp = MemoryPermission()
        assert not mp.can_read("private", "t2", "t1")

    def test_cross_tenant_can_read_shared(self):
        mp = MemoryPermission()
        assert mp.can_read("shared", "t2", "t1")

    def test_cross_tenant_cannot_write(self):
        mp = MemoryPermission()
        assert not mp.can_write("shared", "t2", "t1")

    def test_admin_can_read_anything(self):
        mp = MemoryPermission()
        assert mp.can_read("private", "admin", "t1")
        assert mp.can_read("shared", "admin", "t1")

    def test_admin_can_write_anything(self):
        mp = MemoryPermission()
        assert mp.can_write("private", "admin", "t1")

    def test_filter_memories_mixed_tenants(self):
        mp = MemoryPermission()
        from dataclasses import make_dataclass
        Mem = make_dataclass("Mem", [("scope", str), ("tenant_id", str)])
        memories = [
            Mem(scope="private", tenant_id="t1"),
            Mem(scope="shared", tenant_id="t1"),
            Mem(scope="private", tenant_id="t2"),
            Mem(scope="shared", tenant_id="t2"),
        ]
        filtered = mp.filter_memories(memories, "t1")
        # t1 sees: all t1 memories + shared from t2
        assert len(filtered) == 3
        scopes = [(m.scope, m.tenant_id) for m in filtered]
        assert ("private", "t1") in scopes
        assert ("shared", "t1") in scopes
        assert ("shared", "t2") in scopes
        assert ("private", "t2") not in scopes

    def test_filter_memories_cross_tenant_no_hard_filter(self):
        mp = MemoryPermission()
        from dataclasses import make_dataclass
        Mem = make_dataclass("Mem", [("scope", str), ("tenant_id", str)])
        memories = [
            Mem(scope="private", tenant_id="t2"),
            Mem(scope="shared", tenant_id="t2"),
        ]
        filtered = mp.filter_memories(memories, "t1")
        assert len(filtered) == 1
        assert filtered[0].scope == "shared"

    # ── DB-backed tests ───────────────────────────────────────────

    def test_db_set_scope(self, db_with_scope):
        db = db_with_scope
        db.set_memory_scope("mem-1", "shared", tenant_id="t1")
        assert db.get_memory_scope("mem-1", tenant_id="t1") == "shared"

    def test_db_scope_default_private(self, db_with_scope):
        db = db_with_scope
        assert db.get_memory_scope("mem-1", tenant_id="t1") == "private"

    def test_set_scope_admin_only(self, db_with_scope):
        from tars.security.memory_permission import memory_permission
        # Non-admin can't set scope
        ok, msg = memory_permission.set_scope("mem-1", "shared", "t1")
        assert not ok

    def test_set_scope_admin_succeeds(self, db_with_scope):
        from tars.security.memory_permission import memory_permission
        ok, msg = memory_permission.set_scope("mem-1", "shared", "admin")
        assert ok, msg
        assert db_with_scope.get_memory_scope("mem-1", tenant_id="t1") == "shared"

    def test_set_scope_invalid_value(self, db_with_scope):
        from tars.security.memory_permission import memory_permission
        ok, msg = memory_permission.set_scope("mem-1", "public", "admin")
        assert not ok


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def db_with_scope(tmp_path):
    from tars.database.base import Database
    db_path = tmp_path / "test_scope.db"
    db = Database(str(db_path))
    # Insert a test memory
    db.add_memory(
        content="Test memory content",
        category="fact",
        importance=0.8,
        tenant_id="t1",
        scope="private",
    )
    # Get the just-inserted memory ID
    mems, _ = db.list_recent_memories(page=1, page_size=1, tenant_id="t1")
    # Patch the ID for testing
    if mems:
        conn = db._get_conn()
        conn.cursor().execute("UPDATE memories SET id = 'mem-1' WHERE id = ?", (mems[0].id,))
        conn.commit()
    # Init memory permission
    init_memory_permission(db)
    yield db
    db.close()
