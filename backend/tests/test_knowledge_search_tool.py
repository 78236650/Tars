"""Knowledge search uses org-scoped collection pool."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from tars.database import Database
from tars.knowledge.access import list_collection_targets, search_knowledge
from tars.knowledge.schema import ensure_knowledge_schema
from tars.org import ORG_ID
from tars.tools.builtin.knowledge_search import KnowledgeSearchTool


@pytest.fixture
def db_with_collections(tmp_path):
    db = Database(db_path=str(tmp_path / "knowledge_tool.db"))
    ensure_knowledge_schema(db)
    conn = db._get_conn()
    cursor = conn.cursor()
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    cursor.execute(
        "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("coll-org-a", ORG_ID, "Org KB A", "", now, now),
    )
    cursor.execute(
        "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("coll-legacy", "default", "Legacy KB", "", now, now),
    )
    conn.commit()
    yield db
    db.close()


def test_list_collection_targets_org_scope_only(db_with_collections):
    targets = list_collection_targets(db_with_collections, ORG_ID)
    assert targets == [("coll-org-a", ORG_ID)]


def test_search_uses_org_tenant_for_vectors(db_with_collections):
    retriever = MagicMock()
    retriever.vector_store = MagicMock(is_available=True)
    retriever.retrieve.return_value = []

    search_knowledge(db_with_collections, retriever, "hello", tenant_id=ORG_ID)

    calls = retriever.retrieve.call_args_list
    tenant_by_coll = {c.kwargs["collection_ids"][0]: c.kwargs["tenant_id"] for c in calls}
    assert tenant_by_coll == {"coll-org-a": ORG_ID}


@pytest.mark.asyncio
async def test_knowledge_search_tool_delegates_to_access(db_with_collections):
    retriever = MagicMock()
    retriever.vector_store = MagicMock(is_available=True)
    retriever.retrieve.return_value = [
        {"text": "doc", "source": {"file_name": "a.md"}, "metadata": {}, "score": 0.9}
    ]
    tool = KnowledgeSearchTool(retriever=retriever, db=db_with_collections)
    result = await tool.execute(query="hello")
    assert result.success is True
    assert retriever.retrieve.call_count >= 1
    assert retriever.retrieve.call_args.kwargs["tenant_id"] == ORG_ID
