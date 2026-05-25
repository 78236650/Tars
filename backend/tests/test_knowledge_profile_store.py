"""profile_store CRUD 单测。"""
import os
import tempfile

import pytest

from tars.database import Database
from tars.knowledge.models import DocProfile, GlossaryItem, QAPair, SectionSummary
from tars.knowledge.profile_store import (
    delete_profile,
    get_profile,
    list_profiles_by_collection,
    save_profile,
)


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmp:
        database = Database(os.path.join(tmp, "tars.db"))
        conn = database._get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            ("c1", "default", "test", "", "2026-05-24", "2026-05-24"),
        )
        cur.execute(
            "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, status, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("d1", "c1", "a.txt", "/tmp/a.txt", ".txt", "ready", "2026-05-24"),
        )
        conn.commit()
        yield database


def _sample_profile(doc_id: str = "d1") -> DocProfile:
    return DocProfile(
        doc_id=doc_id,
        doc_type="policy",
        title="测试制度",
        one_liner="一句话摘要",
        summary="详细摘要内容",
        key_points=["要点1", "要点2"],
        sections=[SectionSummary(section_id="s0", title="总则", summary="章节摘要")],
        key_facts=["事实1"],
        glossary=[GlossaryItem(term="术语", definition="定义")],
        qa_pairs=[QAPair(question="Q?", answer="A.")],
        tags=["制度"],
        confidence=0.85,
        enriched_at="2026-05-24T10:00:00Z",
        model_id="mock/model",
    )


def test_save_and_get_profile(db):
    profile = _sample_profile()
    save_profile(db, profile, tenant_id="default", collection_id="c1")
    loaded = get_profile(db, "d1")
    assert loaded is not None
    assert loaded.title == "测试制度"
    assert loaded.key_points == ["要点1", "要点2"]
    assert loaded.sections[0].title == "总则"
    assert loaded.glossary[0].term == "术语"


def test_update_profile_upsert(db):
    save_profile(db, _sample_profile(), tenant_id="default", collection_id="c1")
    updated = _sample_profile()
    updated.summary = "更新后的摘要"
    save_profile(db, updated, tenant_id="default", collection_id="c1")
    loaded = get_profile(db, "d1")
    assert loaded.summary == "更新后的摘要"


def test_list_profiles_by_collection(db):
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, status, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("d2", "c1", "b.txt", "/tmp/b.txt", ".txt", "ready", "2026-05-24"),
    )
    conn.commit()
    save_profile(db, _sample_profile("d1"), tenant_id="default", collection_id="c1")
    p2 = _sample_profile("d2")
    p2.title = "第二篇"
    save_profile(db, p2, tenant_id="default", collection_id="c1")

    profiles = list_profiles_by_collection(db, "c1")
    assert len(profiles) == 2
    titles = {p.title for p in profiles}
    assert "测试制度" in titles
    assert "第二篇" in titles


def test_delete_profile(db):
    save_profile(db, _sample_profile(), tenant_id="default", collection_id="c1")
    assert get_profile(db, "d1") is not None
    assert delete_profile(db, "d1") is True
    assert get_profile(db, "d1") is None
