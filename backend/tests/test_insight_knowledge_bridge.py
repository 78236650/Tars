"""Tests for InsightForge KnowledgeBridge."""
from unittest.mock import MagicMock

import pytest

from tars.insight.knowledge_bridge import KnowledgeBridge
from tars.insight.metric_answer import MetricAnswer, MetricCitation


def test_metric_answer_serializes_citations():
    c = MetricCitation(
        doc_id="d1",
        title="GMV口径",
        snippet="不含退款",
        source_type="insight_glossary",
        relevance=0.9,
    )
    ans = MetricAnswer(value=100, citations=[c])
    d = ans.to_dict()
    assert d["citations"][0]["doc_id"] == "d1"
    assert d["citations"][0]["title"] == "GMV口径"


def test_enrich_definition_adds_refs():
    bridge = KnowledgeBridge(db=None)
    citations = [
        MetricCitation("d1", "GMV口径", "snippet", "insight_glossary", 0.9),
    ]
    out = bridge.enrich_definition("官方定义", citations)
    assert "[ref:d1|GMV口径]" in out


def test_retrieve_prefers_insight_collection(monkeypatch):
    db = MagicMock()
    bridge = KnowledgeBridge(db=db, retriever=MagicMock())

    calls = []

    def fake_search(db_arg, retriever, query, tenant_id="default", collection_id=None, top_k=5):
        calls.append(collection_id)
        if collection_id and collection_id.startswith("insight_"):
            return "", [
                {
                    "id": "chunk1",
                    "text": "GMV 不含退款订单",
                    "score": 0.95,
                    "source": {"file_name": "说明书.md", "doc_id": "insight-doc"},
                    "metadata": {},
                }
            ]
        return "", [
            {
                "id": "chunk2",
                "text": "会议记录",
                "score": 0.5,
                "source": {"file_name": "会议.md", "doc_id": "meet-doc"},
                "metadata": {},
            }
        ]

    monkeypatch.setattr("tars.insight.knowledge_bridge.search_knowledge", fake_search)
    citations = bridge.retrieve_for_question("tenant1", "ds-1", "GMV口径是什么")
    assert citations
    assert citations[0].doc_id == "insight-doc"
    assert citations[0].source_type == "insight_glossary"
    assert calls[0] == "insight_ds-1"
