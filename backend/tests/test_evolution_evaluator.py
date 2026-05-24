"""ResponseEvaluator unit tests."""
from tars.evolution.evaluator import FeedbackType, ResponseEvaluator


def test_evaluate_implicit_returns_scores():
    ev = ResponseEvaluator()
    result = ev.evaluate(
        query="什么是 GMV",
        response="GMV 是成交总额",
        context={"tools_used": ["knowledge_search"]},
    )
    assert 0.0 <= result.overall_score <= 1.0
    assert result.feedback_type == FeedbackType.IMPLICIT


def test_evaluate_explicit_negative_feedback():
    ev = ResponseEvaluator()
    result = ev.evaluate(
        query="hello",
        response="bad",
        explicit_feedback="negative",
    )
    assert result.feedback_type.name == "EXPLICIT"


def test_history_statistics_empty():
    ev = ResponseEvaluator()
    stats = ev.get_history_statistics()
    assert stats["total"] == 0
