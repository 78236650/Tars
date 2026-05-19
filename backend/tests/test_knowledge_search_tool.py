"""Knowledge search must use correct vector tenant per collection."""
import pytest
from unittest.mock import MagicMock

from tars.database import Database
from tars.knowledge.access import list_collection_targets, search_knowledge
from tars.tools.builtin.knowledge_search import KnowledgeSearchTool


@pytest.fixture
def db_with_collections(tmp_path):
    db = Database(db_path=str(tmp_path / "knowledge_tool.db"))
    conn = db._get_conn()
    cursor = conn.cursor()
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    cursor.execute(
        "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("coll-user", "user-abc", "User KB", "", now, now),
    )
    cursor.execute(
        "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("coll-default", "default", "Default KB", "", now, now),
    )
    conn.commit()
    yield db
    db.close()


def test_list_collection_targets_merges_shared_default(db_with_collections):
    targets = list_collection_targets(db_with_collections, "user-abc")
    assert ("coll-user", "user-abc") in targets
    assert ("coll-default", "default") in targets


def test_search_uses_owner_tenant_for_vectors(db_with_collections):
    retriever = MagicMock()
    retriever.retrieve.return_value = []

    search_knowledge(db_with_collections, retriever, "hello", tenant_id="user-abc")

    calls = retriever.retrieve.call_args_list
    tenant_by_coll = {c.kwargs["collection_ids"][0]: c.kwargs["tenant_id"] for c in calls}
    assert tenant_by_coll["coll-user"] == "user-abc"
    assert tenant_by_coll["coll-default"] == "default"


@pytest.mark.asyncio
async def test_knowledge_search_tool_delegates_to_access(db_with_collections):
    retriever = MagicMock()
    retriever.retrieve.return_value = [
        {"text": "doc", "source": {"file_name": "a.md"}, "metadata": {}, "score": 0.9}
    ]
    tool = KnowledgeSearchTool(retriever=retriever, db=db_with_collections)
    result = await tool.execute(query="hello", tenant_id="user-abc")
    assert result.success is True
    assert retriever.retrieve.call_count >= 1
