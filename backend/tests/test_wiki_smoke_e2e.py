"""Task 11 smoke: wiki API + upload routing + read_wiki tool (no live server)."""
import io
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from tars.api.knowledge import (
    clear_wiki_upload_routing,
    init_knowledge_api,
    init_wiki_upload_routing,
    router as knowledge_router,
)
from tars.api.wiki import create_wiki_router
from tars.database import Database
from tars.tools.builtin.wiki_read import WikiReadTool
from tars.wiki.compiler import WikiCompiler
from tars.wiki.events import WikiEventHandler
from tars.wiki.router import WikiRagRouter
from tars.wiki.store import WikiStore

from tests.conftest import setup_knowledge_auth


class _FakeEmbedding:
    def encode(self, texts):
        return [[0.1, 0.2] for _ in texts]


@pytest.fixture
def wiki_stack(tmp_path):
    store = WikiStore(wiki_dir=tmp_path / "wiki")
    mock_llm = AsyncMock(
        return_value=(
            '{"action": "create", "page_name": "ops-notes", '
            '"content": "# 运营笔记\\n\\n泊位 A 已分配", '
            '"summary": "运营笔记"}'
        )
    )
    compiler = WikiCompiler(store=store, llm_provider=mock_llm)
    handler = WikiEventHandler(compiler=compiler)
    router = WikiRagRouter(llm_provider=None)
    tool = WikiReadTool(store=store)
    return store, handler, router, tool


@pytest.mark.asyncio
async def test_read_wiki_tool_after_compile(wiki_stack):
    store, handler, _router, tool = wiki_stack
    await handler.on_small_file_uploaded("泊位 A 分配给 XX 轮", "周例会纪要.md")
    result = await tool.execute(page_name="ops-notes")
    assert result.success
    assert "泊位" in result.output


def test_wiki_api_lists_compiled_page(wiki_stack):
    import asyncio

    store, handler, _router, _tool = wiki_stack
    asyncio.run(handler.on_small_file_uploaded("test", "note.md"))
    app = FastAPI()
    app.include_router(create_wiki_router(store), prefix="/api/wiki")
    client = TestClient(app)
    resp = client.get("/api/wiki/")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()["pages"]]
    assert "ops-notes" in names


def test_upload_routes_small_md_to_wiki(wiki_stack, tmp_path):
    clear_wiki_upload_routing()
    store, handler, wiki_router, _tool = wiki_stack
    db = Database(str(tmp_path / "kb.db"))
    app = FastAPI()
    app.include_router(knowledge_router)
    init_knowledge_api(db, vector_store=None, embedding_provider=_FakeEmbedding())
    init_wiki_upload_routing(handler, wiki_router=wiki_router)
    auth_headers, _user = setup_knowledge_auth(db)
    client = TestClient(app)

    coll = client.post(
        "/api/knowledge/collections",
        json={"name": "test-coll"},
        headers=auth_headers,
    )
    assert coll.status_code == 200
    coll_id = coll.json()["collection"]["id"]

    content = "# 周例会\n\n今天讨论泊位分配。".encode("utf-8")
    resp = client.post(
        f"/api/knowledge/collections/{coll_id}/documents",
        files={"file": ("周例会纪要.md", io.BytesIO(content), "text/markdown")},
        params={"target": "auto"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("routed_to") == "wiki"
    assert body.get("success") is True
    clear_wiki_upload_routing()
