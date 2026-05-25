"""v4.4 知识库深度入库：schema 迁移与领域模型单测。"""
import os
import sqlite3
import tempfile

import pytest

from tars.database import Database
from tars.knowledge.models import (
    DocProfile,
    DocumentSection,
    GlossaryItem,
    MetricsTable,
    ParsedDocument,
    QAPair,
    SectionSummary,
)


@pytest.fixture
def tmp_db_path():
    with tempfile.TemporaryDirectory() as tmp:
        yield os.path.join(tmp, "tars.db")


def test_new_database_has_v44_columns(tmp_db_path):
    db = Database(tmp_db_path)
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO document_collections (id, tenant_id, name, description, default_doc_type, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("c1", "default", "t", "", "policy", "2026-05-24", "2026-05-24"),
    )
    cur.execute(
        "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, status, "
        "doc_type, profile_ready, one_liner, status_message, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("d1", "c1", "x.txt", "/tmp/x.txt", ".txt", "pending", "generic", 0, None, None, "2026-05-24"),
    )
    conn.commit()

    row = db.get_document_file("d1")
    assert row is not None
    assert row["doc_type"] == "generic"
    assert row["profile_ready"] is False
    assert row["status_message"] is None

    assert db.update_document_file("d1", status="ready", profile_ready=True, one_liner="hi")
    row = db.get_document_file("d1")
    assert row["status"] == "ready"
    assert row["profile_ready"] is True
    assert row["one_liner"] == "hi"

    # document_profiles 表必须存在
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_profiles'")
    assert cur.fetchone() is not None


def test_legacy_database_migrates_in_place(tmp_db_path):
    """旧库（无 v4.4 新字段）首次连接应自动迁移。"""
    conn = sqlite3.connect(tmp_db_path)
    conn.execute(
        "CREATE TABLE document_collections (id TEXT PRIMARY KEY, tenant_id TEXT, name TEXT, "
        "description TEXT, created_at TEXT, updated_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE document_files (id TEXT PRIMARY KEY, collection_id TEXT, file_name TEXT, "
        "file_path TEXT, file_type TEXT, chunk_count INTEGER DEFAULT 0, "
        "status TEXT DEFAULT 'pending', created_at TEXT)"
    )
    conn.execute(
        "INSERT INTO document_collections VALUES (?,?,?,?,?,?)",
        ("c1", "default", "t", "", "2026-05-24", "2026-05-24"),
    )
    conn.execute(
        "INSERT INTO document_files VALUES (?,?,?,?,?,?,?,?)",
        ("d1", "c1", "x.txt", "/p", ".txt", 0, "pending", "2026-05-24"),
    )
    conn.commit()
    conn.close()

    db = Database(tmp_db_path)
    row = db.get_document_file("d1")
    assert row["doc_type"] == "generic"
    assert row["profile_ready"] is False
    assert db.update_document_file("d1", status="ready", profile_ready=True)


def test_parsed_document_round_trip():
    pd = ParsedDocument(
        plain_text="hi",
        sections=[DocumentSection(section_id="s0", title="T", text="abc", level=1, page_or_slide=1)],
        doc_type_hint="policy",
        parse_warnings=["w1"],
        metrics_tables=[
            MetricsTable(
                sheet_name="S1",
                headers=["a", "b"],
                rows=[{"a": 1, "b": "x"}],
                inferred_schema={"a": "number", "b": "text"},
            )
        ],
    )
    restored = ParsedDocument.from_dict(pd.to_dict())
    assert restored.to_dict() == pd.to_dict()


def test_doc_profile_round_trip():
    profile = DocProfile(
        doc_id="d1",
        doc_type="policy",
        title="T",
        one_liner="oneliner",
        summary="s",
        key_points=["k1", "k2"],
        sections=[SectionSummary(section_id="s0", title="T", summary="x", key_facts=["kf"], page_or_slide=2)],
        key_facts=["kf"],
        glossary=[GlossaryItem(term="G", definition="D")],
        qa_pairs=[QAPair(question="q", answer="a")],
        tags=["tag"],
        confidence=0.7,
        enriched_at="2026-05-24T10:00:00Z",
        model_id="ollama/llama3",
        token_usage={"in": 100, "out": 50},
        parse_warnings=["truncated"],
    )
    restored = DocProfile.from_dict(profile.to_dict())
    assert restored.to_dict() == profile.to_dict()
