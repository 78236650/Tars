"""Performance tracking for InsightForge Profile pipeline."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ProfilePerfTracker:
    """Track phase timings and counters for insight_snapshot.perf."""

    parallelism: int = 1
    _phase_starts: Dict[str, float] = field(default_factory=dict)
    phases_ms: Dict[str, int] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)
    synthesize: Dict[str, Any] = field(default_factory=dict)
    _start: float = field(default_factory=time.time)

    def mark_phase(self, name: str) -> None:
        now = time.time()
        if name in self._phase_starts:
            elapsed = int((now - self._phase_starts[name]) * 1000)
            self.phases_ms[name] = self.phases_ms.get(name, 0) + elapsed
        self._phase_starts[name] = now

    def end_phase(self, name: str) -> None:
        if name in self._phase_starts:
            elapsed = int((time.time() - self._phase_starts[name]) * 1000)
            self.phases_ms[name] = self.phases_ms.get(name, 0) + elapsed
            del self._phase_starts[name]

    def inc_counter(self, key: str, n: int = 1) -> None:
        self.stats[key] = int(self.stats.get(key, 0)) + n

    def set_stat(self, key: str, value: Any) -> None:
        self.stats[key] = value

    def set_synthesize(self, key: str, value: Any) -> None:
        self.synthesize[key] = value

    def merge_stats(self, extra: Dict[str, Any]) -> None:
        for k, v in extra.items():
            if k in self.stats and isinstance(v, int) and isinstance(self.stats[k], int):
                self.stats[k] = self.stats[k] + v
            else:
                self.stats[k] = v

    def to_dict(self) -> Dict[str, Any]:
        total_ms = int((time.time() - self._start) * 1000)
        return {
            "total_ms": total_ms,
            "phases_ms": dict(self.phases_ms),
            "stats": dict(self.stats),
            "synthesize": dict(self.synthesize),
        }
