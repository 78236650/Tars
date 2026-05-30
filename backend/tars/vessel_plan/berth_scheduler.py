from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .models import Assignment, Berth, Voyage


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _fmt_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
    return dt.isoformat()


@dataclass
class ScheduleInput:
    berths: List[Berth]
    voyages: List[Voyage]
    locked: Dict[str, Assignment] = field(default_factory=dict)
    feasible_berths: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class ScheduleResult:
    assignments: List[Assignment]
    total_wait_min: float
    warnings: List[str]


class BerthScheduler:
    """贪心泊位调度：最小化等待，次优堆场距离。"""

    def __init__(self, yard_lambda: float = 0.15):
        self.yard_lambda = yard_lambda

    def _berth_fits(self, berth: Berth, voyage: Voyage) -> bool:
        return voyage.draft_m <= berth.depth_m and voyage.length_m <= berth.length_m

    def _yard_penalty(self, berth: Berth, voyage: Voyage) -> float:
        return 0.0 if berth.yard_zone == voyage.target_yard_zone else 60.0

    def _berth_free_at(self, timeline: Dict[str, datetime], berth_id: str, default: datetime) -> datetime:
        return timeline.get(berth_id, default)

    def solve(self, inp: ScheduleInput) -> ScheduleResult:
        berths_by_id = {b.id: b for b in inp.berths}
        timeline: Dict[str, datetime] = {}
        assignments: List[Assignment] = []
        warnings: List[str] = []
        total_wait = 0.0

        # 锁定计划先占位
        for voyage_id, locked in inp.locked.items():
            if not locked.berth_id or not locked.etb or not locked.etd:
                continue
            etb = _parse_dt(locked.etb)
            etd = _parse_dt(locked.etd)
            timeline[locked.berth_id] = max(timeline.get(locked.berth_id, etb), etd)
            assignments.append(locked)

        sorted_voyages = sorted(
            inp.voyages,
            key=lambda v: (-v.priority, v.eta),
        )

        for voyage in sorted_voyages:
            if voyage.id in inp.locked:
                continue

            eta = _parse_dt(voyage.eta)
            allowed_ids = inp.feasible_berths.get(voyage.id)
            candidates = [
                b
                for b in inp.berths
                if self._berth_fits(b, voyage)
                and (allowed_ids is None or b.id in allowed_ids)
            ]
            if not candidates:
                warnings.append(f"{voyage.vessel_name} 无可用泊位（吃水/船长约束）")
                assignments.append(
                    Assignment(
                        voyage_id=voyage.id,
                        berth_id=None,
                        etb=None,
                        etd=None,
                        wait_min=0,
                        yard_penalty=0,
                        score=9999,
                        source="or",
                        locked=False,
                    )
                )
                continue

            best: Optional[tuple] = None
            for berth in candidates:
                free_at = self._berth_free_at(timeline, berth.id, eta)
                etb = max(eta, free_at)
                etd = etb + timedelta(hours=voyage.service_hours)
                wait_min = max(0.0, (etb - eta).total_seconds() / 60.0)
                yard_pen = self._yard_penalty(berth, voyage)
                score = wait_min + self.yard_lambda * yard_pen
                if best is None or score < best[0]:
                    best = (score, berth, etb, etd, wait_min, yard_pen)

            assert best is not None
            _, berth, etb, etd, wait_min, yard_pen = best
            timeline[berth.id] = etd
            total_wait += wait_min
            if wait_min > 240:
                warnings.append(f"{voyage.vessel_name} 等待超过 4 小时（{wait_min:.0f} 分钟）")
            assignments.append(
                Assignment(
                    voyage_id=voyage.id,
                    berth_id=berth.id,
                    etb=_fmt_dt(etb),
                    etd=_fmt_dt(etd),
                    wait_min=wait_min,
                    yard_penalty=yard_pen,
                    score=best[0],
                    source="or",
                    locked=False,
                )
            )

        return ScheduleResult(assignments=assignments, total_wait_min=total_wait, warnings=warnings)
