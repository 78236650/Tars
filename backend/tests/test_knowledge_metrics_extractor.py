"""metrics 专路单测。"""
import pytest

from tars.knowledge.metrics_extractor import (
    build_metrics_profile,
    tables_to_key_facts,
)
from tars.knowledge.models import MetricsTable, ParsedDocument


def test_tables_to_key_facts_formats_rows():
    table = MetricsTable(
        sheet_name="KPI",
        headers=["指标", "口径"],
        rows=[{"指标": "GMV", "口径": "含税"}],
    )
    facts = tables_to_key_facts([table])
    assert len(facts) == 1
    assert "GMV" in facts[0]
    assert "含税" in facts[0]


def test_build_metrics_profile_sections():
    tables = [
        MetricsTable(sheet_name="Sheet1", headers=["a"], rows=[{"a": 1}, {"a": 2}]),
        MetricsTable(sheet_name="Sheet2", headers=["b"], rows=[{"b": "x"}]),
    ]
    parsed = ParsedDocument(metrics_tables=tables, doc_type_hint="metrics")
    profile = build_metrics_profile(parsed, doc_id="m1", file_name="data.xlsx")
    assert len(profile.sections) == 2
    assert profile.doc_type == "metrics"
    assert profile.key_facts
