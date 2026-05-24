"""PromptTuner unit tests."""
from datetime import datetime

from tars.evolution.evaluator import ConversationRecord, EvaluationResult, FeedbackType
from tars.evolution.prompt_tuner import PromptTuner


def _low_eval() -> EvaluationResult:
    return EvaluationResult(
        overall_score=0.4,
        relevance=0.4,
        completeness=0.4,
        accuracy=0.4,
        style_match=0.4,
        tool_efficiency=0.4,
        feedback_type=FeedbackType.IMPLICIT,
    )


def _make_history(prompt_type: str, count: int, *, score: float = 0.4) -> list[ConversationRecord]:
    records = []
    for i in range(count):
        ev = _low_eval()
        ev.overall_score = score
        ev.relevance = score
        ev.completeness = score
        ev.style_match = score
        records.append(
            ConversationRecord(
                conversation_id=f"c{i}",
                query="q",
                response="a",
                timestamp=datetime.now(),
                evaluation=ev,
                context={"prompt_type": prompt_type},
            )
        )
    return records


def test_get_current_prompt_returns_default():
    tuner = PromptTuner()
    text = tuner.get_current_prompt("master")
    assert "TARS" in text


def test_tune_skips_when_insufficient_history():
    tuner = PromptTuner()
    before = tuner.get_current_prompt("master")
    out = tuner.tune_system_prompt(_make_history("master", 5), "master")
    assert out == before
    assert len(tuner.prompt_versions["master"]) == 1


def test_tune_appends_version_on_low_scores():
    tuner = PromptTuner()
    history = _make_history("master", 25, score=0.4)
    improved = tuner.tune_system_prompt(history, "master")
    assert improved != tuner.prompt_versions["master"][0].prompt_text
    assert "relevant" in improved.lower() or "complete" in improved.lower()
    assert len(tuner.prompt_versions["master"]) == 2


def test_tune_keeps_prompt_when_avg_score_high():
    tuner = PromptTuner()
    before = tuner.get_current_prompt("code")
    out = tuner.tune_system_prompt(_make_history("code", 25, score=0.9), "code")
    assert out == before
    assert len(tuner.prompt_versions["code"]) == 1


def test_record_feedback_updates_success_rate():
    tuner = PromptTuner()
    ev = _low_eval()
    ev.overall_score = 0.8
    tuner.record_feedback("master", ev)
    history = tuner.get_prompt_history("master")
    assert history[-1]["usage_count"] == 1
    assert history[-1]["success_rate"] == 0.8


def test_rollback_prompt_creates_new_version():
    tuner = PromptTuner()
    history = _make_history("writing", 25, score=0.3)
    tuner.tune_system_prompt(history, "writing")
    assert len(tuner.prompt_versions["writing"]) == 2
    original = tuner.prompt_versions["writing"][0].prompt_text
    assert tuner.rollback_prompt("writing", 1)
    assert tuner.get_current_prompt("writing") == original
    assert len(tuner.prompt_versions["writing"]) == 3
