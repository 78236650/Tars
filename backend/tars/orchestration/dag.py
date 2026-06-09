"""DAG validation for multi-agent orchestration (v5.0.5/A5).

Detects cyclic dependencies before execution so the orchestrator fails fast
instead of dead-locking or looping. Operates on a generic adjacency mapping:
``{node_id: [dependency_ids...]}``.
"""

from __future__ import annotations

from typing import Dict, Hashable, Iterable, List, Sequence


class CyclicDependencyError(ValueError):
    """Raised when the dependency graph contains a cycle."""

    def __init__(self, cycle: Sequence[Hashable]):
        self.cycle = list(cycle)
        super().__init__(
            "检测到循环依赖: " + " -> ".join(str(n) for n in self.cycle)
        )


def detect_cycle(deps: Dict[Hashable, Iterable[Hashable]]) -> List[Hashable]:
    """Return a node sequence forming a cycle, or [] if the graph is acyclic.

    ``deps`` maps each node to the nodes it depends on. Missing nodes referenced
    as dependencies are treated as terminal (no further edges).
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[Hashable, int] = {n: WHITE for n in deps}
    stack: List[Hashable] = []

    def visit(node: Hashable) -> List[Hashable]:
        color[node] = GRAY
        stack.append(node)
        for dep in deps.get(node, []) or []:
            if dep not in color:
                # dependency on an undefined node — terminal, no edge to follow
                continue
            if color[dep] == GRAY:
                # found a back-edge: extract the cycle from the stack
                idx = stack.index(dep)
                return stack[idx:] + [dep]
            if color[dep] == WHITE:
                found = visit(dep)
                if found:
                    return found
        color[node] = BLACK
        stack.pop()
        return []

    for n in list(deps.keys()):
        if color[n] == WHITE:
            found = visit(n)
            if found:
                return found
    return []


def validate_acyclic(deps: Dict[Hashable, Iterable[Hashable]]) -> None:
    """Raise CyclicDependencyError if the dependency graph has a cycle."""
    cycle = detect_cycle(deps)
    if cycle:
        raise CyclicDependencyError(cycle)
