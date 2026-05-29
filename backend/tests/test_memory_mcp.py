"""Task 10: Memory MCP 测试。"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp"))
from tars_memory_server import _search_memory, _add_memory


def test_mcp_add_and_search(tmp_path, monkeypatch):
    monkeypatch.setenv("TARS_DATA_DIR", str(tmp_path))
    _add_memory(content="user prefers dark mode", category="user_preference", tenant="t")
    out = _search_memory(query="dark mode", tenant="t", limit=5)
    assert "dark mode" in out
