"""Unit tests for DAG cycle detection (v5.0.5/A5)."""

import pytest

from tars.orchestration.dag import (
    CyclicDependencyError,
    detect_cycle,
    validate_acyclic,
)


def test_acyclic_graph_returns_empty():
    deps = {"a": ["b"], "b": ["c"], "c": []}
    assert detect_cycle(deps) == []
    validate_acyclic(deps)  # must not raise


def test_empty_graph_is_acyclic():
    assert detect_cycle({}) == []
    validate_acyclic({})


def test_simple_cycle_detected():
    deps = {"a": ["b"], "b": ["a"]}
    cycle = detect_cycle(deps)
    assert cycle, "expected a non-empty cycle"
    # a back-edge closes the loop: first and last node coincide
    assert cycle[0] == cycle[-1]


def test_self_loop_detected():
    cycle = detect_cycle({"a": ["a"]})
    assert cycle == ["a", "a"]


def test_longer_cycle_detected():
    deps = {"a": ["b"], "b": ["c"], "c": ["a"]}
    cycle = detect_cycle(deps)
    assert cycle and cycle[0] == cycle[-1]
    assert set(cycle) == {"a", "b", "c"}


def test_dependency_on_undefined_node_is_terminal():
    # "b" is referenced but never defined as a key — treated as terminal.
    deps = {"a": ["b"]}
    assert detect_cycle(deps) == []
    validate_acyclic(deps)


def test_disconnected_components_one_cyclic():
    deps = {"a": ["b"], "b": [], "x": ["y"], "y": ["x"]}
    cycle = detect_cycle(deps)
    assert set(cycle) <= {"x", "y"}
    assert cycle and cycle[0] == cycle[-1]


def test_validate_acyclic_raises_with_cycle_in_message():
    deps = {"a": ["b"], "b": ["a"]}
    with pytest.raises(CyclicDependencyError) as exc_info:
        validate_acyclic(deps)
    assert exc_info.value.cycle  # cycle attribute populated
    assert "循环依赖" in str(exc_info.value)
