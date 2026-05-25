"""Whisper hallucination filter tests."""
from tars.meeting.transcript import filter_whisper_hallucinations


def test_filters_prompt_echo_lines():
    raw = "\n".join(["请使用简体中文标点。"] * 5 + ["今天开会讨论预算。"])
    out = filter_whisper_hallucinations(
        raw,
        initial_prompt="以下是普通话句子，请使用简体中文输出，并加上合适的中文标点。",
    )
    assert "请使用简体中文标点" not in out
    assert "今天开会讨论预算" in out


def test_dedupes_consecutive_identical_lines():
    raw = "你好。\n你好。\n世界。"
    assert filter_whisper_hallucinations(raw) == "你好。\n世界。"
