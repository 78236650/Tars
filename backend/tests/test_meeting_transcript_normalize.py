"""Transcript normalization (Traditional -> Simplified)."""
import pytest

zhconv = pytest.importorskip("zhconv")

from tars.meeting.transcript import normalize_transcript_text


def test_normalize_transcript_to_simplified():
    traditional = "這是一個測試，我們討論會議助手。"
    simplified = normalize_transcript_text(traditional, to_simplified=True)
    assert "这" in simplified
    assert "测试" in simplified
    assert "這" not in simplified


def test_normalize_skipped_when_disabled():
    text = "這是繁體"
    assert normalize_transcript_text(text, to_simplified=False) == text
