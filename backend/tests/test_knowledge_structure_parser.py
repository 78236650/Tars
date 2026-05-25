"""structure_parser 单测（Phase 1 + infer_doc_type）。"""
import os
import tempfile

import pytest

from tars.knowledge.structure_parser import infer_doc_type, parse_to_document


def test_infer_doc_type_by_extension():
    assert infer_doc_type("data.xlsx", ".xlsx") == "metrics"
    assert infer_doc_type("deck.pptx", ".pptx") == "proposal"
    assert infer_doc_type("制度.docx", ".docx") == "policy"
    assert infer_doc_type("readme.md", ".md") == "generic"


def test_infer_doc_type_explicit_override():
    assert infer_doc_type("x.txt", ".txt", explicit="proposal") == "proposal"


def test_parse_to_document_txt(tmp_path):
    p = tmp_path / "sample.txt"
    p.write_text("Hello knowledge ingest", encoding="utf-8")
    parsed = parse_to_document(str(p), doc_type="generic")
    assert "Hello" in parsed.plain_text
    assert len(parsed.sections) >= 1
    assert parsed.doc_type_hint == "generic"
