"""KnowledgeEnricher 单测 — mock LLM provider。"""
import json
from unittest.mock import MagicMock

import pytest

from tars.knowledge.enricher import enrich_document
from tars.knowledge.enricher_prompts import build_enrich_prompt
from tars.knowledge.metrics_extractor import build_metrics_profile, tables_to_key_facts
from tars.knowledge.models import DocumentSection, MetricsTable, ParsedDocument


class _MockLlmSettingsStore:
    def __init__(self, provider):
        self._provider = provider

    def get(self, tenant_id: str):
        return {"tenant_id": tenant_id}


def _mock_provider(json_payload: dict):
    provider = MagicMock()
    provider.complete.return_value = json.dumps(json_payload, ensure_ascii=False)
    return provider


def test_build_policy_prompt_contains_doc_type():
    prompt = build_enrich_prompt(doc_type="policy", sample="正文", file_name="制度.txt")
    assert "policy" in prompt or "制度" in prompt
    assert "正文" in prompt


def test_enrich_document_returns_full_profile():
    payload = {
        "title": "仓储制度",
        "one_liner": "规范仓储流程",
        "summary": "本文档规定入库出库流程。",
        "key_points": ["入库需审批", "出库需盘点"],
        "key_facts": ["审批权限：主管"],
        "tags": ["仓储"],
        "qa_pairs": [{"question": "谁审批?", "answer": "主管"}],
        "glossary": [{"term": "安全库存", "definition": "最低存量"}],
    }
    provider = _mock_provider(payload)

    class _Store:
        def get(self, tenant_id):
            return {}

    parsed = ParsedDocument(
        plain_text="制度全文内容",
        sections=[DocumentSection(section_id="s0", title="总则", text="制度全文内容")],
        doc_type_hint="policy",
    )

    from tars.knowledge import enricher as enricher_mod

    original = enricher_mod._resolve_provider

    def _fake_resolve(tenant_id, store):
        return provider, {"label": "mock/model"}

    enricher_mod._resolve_provider = _fake_resolve
    try:
        profile = enrich_document(
            parsed,
            tenant_id="default",
            doc_id="doc-1",
            doc_type="policy",
            llm_settings_store=_Store(),
            file_name="制度.txt",
        )
    finally:
        enricher_mod._resolve_provider = original

    assert profile is not None
    assert profile.title == "仓储制度"
    assert profile.one_liner == "规范仓储流程"
    assert profile.key_points == ["入库需审批", "出库需盘点"]
    assert profile.qa_pairs[0].question == "谁审批?"
    assert profile.confidence > 0


def test_enrich_document_no_provider_returns_none():
    parsed = ParsedDocument(plain_text="hello")
    from tars.knowledge import enricher as enricher_mod

    original = enricher_mod._resolve_provider
    enricher_mod._resolve_provider = lambda tenant_id, store: (None, {})
    try:
        profile = enrich_document(
            parsed,
            tenant_id="default",
            doc_id="d1",
            doc_type="generic",
            llm_settings_store=None,
        )
    finally:
        enricher_mod._resolve_provider = original
    assert profile is None


@pytest.mark.asyncio
async def test_llm_complete_async_chat_provider():
    from tars.knowledge.enricher import _llm_complete
    from tars.models.base import ChatMessage, ModelResponse

    class _AsyncChatProvider:
        async def chat(self, messages: List[ChatMessage], **kwargs):
            assert messages[0].content == "hello"
            return ModelResponse(content='{"title":"t","one_liner":"o","summary":"s"}', model="test")

    text = _llm_complete(_AsyncChatProvider(), "hello")
    assert text and "title" in text


def test_metrics_profile_from_tables():
    table = MetricsTable(
        sheet_name="KPI",
        headers=["指标", "口径"],
        rows=[{"指标": "GMV", "口径": "含税销售额"}],
    )
    parsed = ParsedDocument(metrics_tables=[table], doc_type_hint="metrics")
    profile = build_metrics_profile(parsed, doc_id="m1", file_name="metrics.xlsx")
    assert profile.doc_type == "metrics"
    assert profile.key_facts
    assert "GMV" in profile.key_facts[0]
    assert profile.confidence >= 0.9


def test_tables_to_key_facts():
    table = MetricsTable(
        sheet_name="S1",
        headers=["a", "b"],
        rows=[{"a": 1, "b": "x"}, {"a": 2, "b": "y"}],
    )
    facts = tables_to_key_facts([table])
    assert len(facts) == 2
    assert "a=1" in facts[0]
