"""KnowledgePublisher behaviour: publish failure surfaced, cross-tenant rewrite rejected, file versioning."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from tars.database import Database
from tars.insight.knowledge_publisher import KnowledgePublisher


class StubIndexerOk:
    def index_document(self, **kwargs):
        return {"status": "indexed", "chunks": 1}


class StubIndexerFail:
    def __init__(self):
        self.called = False

    def index_document(self, **kwargs):
        self.called = True
        return {"status": "failed", "error": "embedder offline"}


@pytest.fixture
def db(tmp_path):
    return Database(db_path=str(tmp_path / "kb.db"))


def test_publish_indexed_returns_doc_id(db):
    p = KnowledgePublisher(db, knowledge_indexer=StubIndexerOk())
    doc = p.publish("ds1", "Demo", "t1", "# markdown")
    assert doc is not None


def test_publish_failed_returns_none(db):
    indexer = StubIndexerFail()
    p = KnowledgePublisher(db, knowledge_indexer=indexer)
    doc = p.publish("ds1", "Demo", "t1", "# markdown")
    assert doc is None
    assert indexer.called


def test_publish_uses_run_id_in_filename(db, caplog):
    """Filename should embed run_id[:8] when provided."""
    captured = {}

    class CaptureIndexer:
        def index_document(self, **kwargs):
            captured.update(kwargs)
            return {"status": "indexed"}

    p = KnowledgePublisher(db, knowledge_indexer=CaptureIndexer())
    p.publish("ds1", "Demo", "t1", "# md", run_id="abcdef1234567890")
    assert captured.get("file_name") == "insightforge_Demo_vabcdef12.md"


def test_ensure_collection_rejects_cross_tenant_rewrite(db):
    p = KnowledgePublisher(db, knowledge_indexer=None)
    p.ensure_collection("c1", "name", "t1")
    with pytest.raises(PermissionError):
        p.ensure_collection("c1", "name", "t2")


def test_ensure_collection_idempotent_same_tenant(db):
    p = KnowledgePublisher(db, knowledge_indexer=None)
    p.ensure_collection("c1", "name", "t1")
    # second call same tenant should be a no-op
    p.ensure_collection("c1", "name", "t1")
