"""Memory permission checker — v4.0.0 Phase 1.

Enforces scope-based access control: private memories are tenant-only,
shared memories are visible across tenants.
"""
from enum import Enum
from typing import Optional


class MemoryScope(str, Enum):
    PRIVATE = "private"
    SHARED = "shared"


class MemoryPermission:
    """Check whether a given user/tenant can access a memory.

    Rules:
      - Same tenant: full read/write access to private + shared.
      - Cross-tenant: can only read shared memories of other tenants.
      - Admin (tenant_id="admin"): bypass all checks.
    """

    def __init__(self, db=None):
        self._db = db

    def can_read(self, memory_scope: str, requesting_tenant: str, memory_tenant: str) -> bool:
        """Return True if *requesting_tenant* can read a memory with given scope."""
        if requesting_tenant == memory_tenant:
            return True
        if requesting_tenant == "admin":
            return True
        # Cross-tenant: only shared
        return memory_scope == MemoryScope.SHARED.value

    def can_write(self, memory_scope: str, requesting_tenant: str, memory_tenant: str) -> bool:
        """Return True if *requesting_tenant* can modify a memory."""
        if requesting_tenant == "admin":
            return True
        return requesting_tenant == memory_tenant

    def check_read(self, memory_id: str, tenant_id: str) -> tuple:
        """Check read access for a DB memory. Returns (allowed: bool, reason: str)."""
        if not self._db:
            return True, ""
        mem = self._db.find_memory_any_tenant(memory_id)
        if not mem:
            return True, ""  # Memory doesn't exist — let caller handle
        scope = getattr(mem, "scope", "private")
        memory_tenant = mem.tenant_id or "default"

        if self.can_read(scope, tenant_id, memory_tenant):
            return True, ""
        return False, f"权限不足：租户 '{tenant_id}' 无法读取租户 '{memory_tenant}' 的私有记忆"

    def check_write(self, memory_id: str, tenant_id: str) -> tuple:
        """Check write access for a DB memory. Returns (allowed: bool, reason: str)."""
        if not self._db:
            return True, ""
        mem = self._db.find_memory_any_tenant(memory_id)
        if not mem:
            return True, ""  # Memory doesn't exist — let caller handle
        scope = getattr(mem, "scope", "private")
        memory_tenant = mem.tenant_id or "default"

        if self.can_write(scope, tenant_id, memory_tenant):
            return True, ""
        return False, "权限不足：无法修改其他租户的记忆"

    def filter_memories(self, memories: list, tenant_id: str) -> list:
        """Return only memories that *tenant_id* can read."""
        return [
            mem for mem in memories
            if self.can_read(
                getattr(mem, "scope", "private"),
                tenant_id,
                getattr(mem, "tenant_id", "default"),
            )
        ]

    def set_scope(self, memory_id: str, scope: str, tenant_id: str) -> tuple:
        """Admin sets scope. Returns (success: bool, message: str)."""
        if not self._db:
            return False, "DB not initialized"
        if scope not in ("private", "shared"):
            return False, f"无效的 scope: {scope}"
        if tenant_id != "admin":
            return False, "只有管理员可以修改记忆 scope"
        # Look up the memory to get its actual tenant_id
        mem = self._db.find_memory_any_tenant(memory_id)
        if not mem:
            return False, "记忆不存在"
        ok = self._db.set_memory_scope(memory_id, scope, tenant_id=mem.tenant_id or "default")
        return (ok, "已更新" if ok else "记忆不存在")


# ── Global singleton ────────────────────────────────────────────────

memory_permission: Optional[MemoryPermission] = None


def init_memory_permission(db) -> MemoryPermission:
    global memory_permission
    memory_permission = MemoryPermission(db)
    return memory_permission
