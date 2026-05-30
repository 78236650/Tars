from datetime import datetime, timedelta, timezone

from tars.vessel_plan.berth_scheduler import BerthScheduler, ScheduleInput
from tars.vessel_plan.models import Berth, Voyage


def _voyage(vid, eta_h, loa=300, draft=12, zone="A", pri=0, hours=8):
    tz = timezone(timedelta(hours=8))
    eta = datetime(2026, 6, 1, eta_h, 0, tzinfo=tz).isoformat()
    return Voyage(
        vid, vid, vid, eta, None, 800, zone, hours, "pending", loa, draft, pri
    )


def test_no_berth_overlap():
    berths = [
        Berth("b1", "1#", 400, 16, 2, "A", 0, 0),
        Berth("b2", "2#", 400, 16, 2, "B", 120, 0),
    ]
    voyages = [_voyage("v1", 8), _voyage("v2", 9)]
    sched = BerthScheduler(yard_lambda=0.1)
    result = sched.solve(ScheduleInput(berths=berths, voyages=voyages))
    by_berth = {}
    for a in result.assignments:
        assert a.berth_id
        by_berth.setdefault(a.berth_id, []).append((a.etb, a.etd))
    for slots in by_berth.values():
        slots.sort()
        for i in range(1, len(slots)):
            assert slots[i][0] >= slots[i - 1][1]


def test_draft_infeasible_skipped():
    berths = [Berth("b1", "1#", 400, 10.0, 2, "A", 0, 0)]
    voyages = [_voyage("v1", 8, draft=12.0)]
    sched = BerthScheduler()
    result = sched.solve(ScheduleInput(berths=berths, voyages=voyages))
    assert result.assignments[0].berth_id is None
    assert result.warnings
