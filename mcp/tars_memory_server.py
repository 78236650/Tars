"""Task 10: TARS Memory MCP Server — 对外暴露记忆检索/写入。"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from mcp.server.fastmcp import FastMCP
from tars.database.base import Database
from tars.memory.manager import MemoryManager

mcp = FastMCP("tars-memory")


def _manager() -> MemoryManager:
    data_dir = os.environ.get("TARS_DATA_DIR")
    db_path = os.path.join(data_dir, "tars.db") if data_dir else None
    return MemoryManager(db=Database(db_path=db_path))


def _search_memory(query: str, tenant: str = "default", limit: int = 5) -> str:
    hits = _manager().for_tenant(tenant).search_memories(query, limit=limit)
    return "\n".join(getattr(h, "content", str(h)) for h in hits) or "(no results)"


def _add_memory(content: str, category: str = "fact", tenant: str = "default") -> str:
    import asyncio
    asyncio.run(_manager().for_tenant(tenant).add_manual_memory(content, category=category))
    return "saved"


@mcp.tool()
def search_memory(query: str, tenant: str = "default", limit: int = 5) -> str:
    """检索 TARS 长期记忆。"""
    return _search_memory(query, tenant, limit)


@mcp.tool()
def add_memory(content: str, category: str = "fact", tenant: str = "default") -> str:
    """写入一条 TARS 记忆。"""
    return _add_memory(content, category, tenant)


if __name__ == "__main__":
    mcp.run()
