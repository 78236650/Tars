"""Evolution eval runner tests."""
from pathlib import Path

import pytest

from tars.evolution.eval_runner import EvalRunner


@pytest.fixture
def runner():
    return EvalRunner(eval_path=Path(__file__).parent / "evolution" / "eval_set.yaml")


def test_eval_set_has_at_least_20_cases(runner):
    cases = runner.load_cases()
    assert len(cases) >= 20


@pytest.mark.evolution_eval
@pytest.mark.parametrize(
    "ctx,expected_min",
    [
        ({"personality": {"honesty": 0.9, "humor": 0.5, "initiative": 0.7, "empathy": 0.7, "conciseness": 0.7}}, 0.2),
        ({"tools_used": ["shell", "memory"]}, 0.1),
        ({"skill_id": "code-review"}, 0.05),
        ({"subagent": "code"}, 0.05),
        ({"prompts": {"master": "You are TARS, a helpful assistant with enough text."}}, 0.05),
        ({"delegation_weights": {"data": 0.8, "code": 0.2}}, 0.05),
    ],
)
def test_eval_runner_scores_context(runner, ctx, expected_min):
    result = runner.run(ctx)
    assert result["total"] >= 1
    assert result["score"] >= expected_min


def test_eval_compare_improvement_gate(runner):
    before = {"score": 0.5}
    after = {"score": 0.65}
    cmp = runner.compare(before, after)
    assert cmp["improved"] is True
    assert cmp["should_rollback"] is False

    worse = runner.compare({"score": 0.6}, {"score": 0.5})
    assert worse["should_rollback"] is True
