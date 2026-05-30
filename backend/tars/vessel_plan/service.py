from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from .berth_scheduler import BerthScheduler, ScheduleInput
from .models import Assignment
from .repository import VesselPlanRepository
from .seed import seed_demo_port
from .ship_plan_agent import ShipPlanAgent


class VesselPlanService:
    def __init__(self, db, tenant_id: str = "default"):
        self.db = db
        self.tenant_id = tenant_id
        self.repo = VesselPlanRepository(db, tenant_id=tenant_id)
        self.agent = ShipPlanAgent()
        self.scheduler = BerthScheduler(yard_lambda=0.15)

    def ensure_seeded(self) -> dict:
        if self.repo.count_berths() == 0:
            return seed_demo_port(self.db, tenant_id=self.tenant_id)
        return {"berths": self.repo.count_berths(), "seeded": True}

    def reset_demo(self) -> dict:
        return seed_demo_port(self.db, tenant_id=self.tenant_id)

    def demo_status(self) -> dict:
        voyages = self.repo.horizon_voyages(48)
        return {
            "seeded": self.repo.count_berths() > 0,
            "berth_count": self.repo.count_berths(),
            "pending_voyages_48h": len(voyages),
        }

    def optimize(self, horizon_hours: int = 48) -> dict:
        self.ensure_seeded()
        berths = self.repo.list_berths()
        voyages = self.repo.horizon_voyages(horizon_hours)
        constraints = self.agent.preprocess(berths, voyages)
        locked = {k: v for k, v in self.repo.get_assignment_map().items() if v.locked}

        result = self.scheduler.solve(
            ScheduleInput(
                berths=berths,
                voyages=voyages,
                locked=locked,
                feasible_berths=constraints["feasible_berths"],
            )
        )
        all_warnings = constraints["warnings"] + result.warnings
        summary, notes, warnings = self.agent.postprocess(
            berths, voyages, result.assignments, all_warnings
        )

        # 保留 locked，更新其余
        merged = {a.voyage_id: a for a in result.assignments}
        for vid, la in locked.items():
            merged[vid] = la
        self.repo.clear_unlocked_assignments()
        self.repo.save_assignments(list(merged.values()))

        run_id = str(uuid.uuid4())
        self.repo.save_plan_run(
            run_id,
            horizon_hours,
            "min_wait+yard",
            constraints,
            result.total_wait_min,
            summary,
        )
        return self._horizon_payload(
            horizon_hours,
            agent_summary=summary,
            voyage_notes=notes,
            warnings=warnings,
            run_id=run_id,
            total_wait_min=result.total_wait_min,
        )

    def recompute(self, horizon_hours: int = 48) -> dict:
        return self.optimize(horizon_hours=horizon_hours)

    def patch_assignment(
        self,
        voyage_id: str,
        berth_id: Optional[str] = None,
        etb: Optional[str] = None,
        etd: Optional[str] = None,
        locked: Optional[bool] = None,
    ) -> dict:
        self.ensure_seeded()
        existing = self.repo.get_assignment_map().get(voyage_id)
        voyage = self.repo.get_voyage(voyage_id)
        if not voyage:
            raise ValueError("航次不存在")

        a = existing or Assignment(
            voyage_id=voyage_id,
            berth_id=None,
            etb=None,
            etd=None,
            wait_min=0,
            yard_penalty=0,
            score=0,
            source="manual",
            locked=False,
        )
        if berth_id is not None:
            a.berth_id = berth_id
        if etb is not None:
            a.etb = etb
        if etd is not None:
            a.etd = etd
        if locked is not None:
            a.locked = locked
        a.source = "manual"
        self.repo.save_assignments([a])
        return self.get_voyage_detail(voyage_id)

    def get_voyage_detail(self, voyage_id: str) -> dict:
        self.ensure_seeded()
        voyage = self.repo.get_voyage(voyage_id)
        if not voyage:
            raise ValueError("航次不存在")
        berths = self.repo.list_berths()
        berths_by_id = {b.id: b for b in berths}
        amap = self.repo.get_assignment_map()
        a = amap.get(voyage_id)
        berth_name = berths_by_id[a.berth_id].name if a and a.berth_id and a.berth_id in berths_by_id else None
        alts = self.agent.alternatives(voyage, berths, a.berth_id if a else None)
        return {
            "voyage": {
                "id": voyage.id,
                "vessel_name": voyage.vessel_name,
                "eta": voyage.eta,
                "cargo_teu": voyage.cargo_teu,
                "target_yard_zone": voyage.target_yard_zone,
                "service_hours": voyage.service_hours,
                "length_m": voyage.length_m,
                "draft_m": voyage.draft_m,
                "priority": voyage.priority,
            },
            "assignment": self._assignment_dict(a, berth_name) if a else None,
            "alternatives": alts,
            "timeline": self._build_timeline(voyage, a, berth_name),
        }

    def get_horizon(self, horizon_hours: int = 48) -> dict:
        self.ensure_seeded()
        return self._horizon_payload(horizon_hours)

    def _horizon_payload(
        self,
        horizon_hours: int,
        agent_summary: str = "",
        voyage_notes: Optional[Dict[str, str]] = None,
        warnings: Optional[List[str]] = None,
        run_id: Optional[str] = None,
        total_wait_min: float = 0,
    ) -> dict:
        berths = self.repo.list_berths()
        berths_by_id = {b.id: b for b in berths}
        voyages = self.repo.horizon_voyages(horizon_hours)
        amap = self.repo.get_assignment_map()
        notes = voyage_notes or {}
        rows = []
        tw = total_wait_min
        if not tw:
            tw = sum(amap[v.id].wait_min for v in voyages if v.id in amap)

        for v in voyages:
            a = amap.get(v.id)
            berth_name = None
            if a and a.berth_id and a.berth_id in berths_by_id:
                berth_name = berths_by_id[a.berth_id].name
            rows.append(
                {
                    "voyage_id": v.id,
                    "vessel_name": v.vessel_name,
                    "eta": v.eta,
                    "etb": a.etb if a else None,
                    "etd": a.etd if a else None,
                    "berth_id": a.berth_id if a else None,
                    "berth_name": berth_name,
                    "wait_min": a.wait_min if a else 0,
                    "target_yard_zone": v.target_yard_zone,
                    "cargo_teu": v.cargo_teu,
                    "locked": a.locked if a else False,
                    "agent_note": notes.get(v.id, ""),
                }
            )

        return {
            "run_id": run_id,
            "horizon_hours": horizon_hours,
            "berths": [self._berth_dict(b) for b in berths],
            "rows": rows,
            "agent_summary": agent_summary,
            "total_wait_min": tw,
            "warnings": warnings or [],
        }

    async def adopt(self, voyage_ids: List[str], session_id: str, orchestrator) -> dict:
        self.ensure_seeded()
        berths_by_id = {b.id: b for b in self.repo.list_berths()}
        amap = self.repo.get_assignment_map()
        task_ids = []
        goals = []

        for vid in voyage_ids:
            voyage = self.repo.get_voyage(vid)
            a = amap.get(vid)
            if not voyage or not a or not a.berth_id:
                continue
            berth = berths_by_id.get(a.berth_id)
            bname = berth.name if berth else a.berth_id
            etb_short = (a.etb or "")[:16]
            goal = (
                f"安排 {voyage.vessel_name} {etb_short} 靠 {bname} "
                f"{'卸' if voyage.cargo_teu else '作业'} {voyage.cargo_teu} 箱，"
                f"堆场 {voyage.target_yard_zone}"
            )
            result = await orchestrator.orchestrate(session_id=session_id, goal=goal)
            if result.get("task_id"):
                task_ids.append(result["task_id"])
                goals.append(goal)
                self.repo.mark_voyage_dispatched(vid)

        return {"task_ids": task_ids, "goals": goals, "count": len(task_ids)}

    @staticmethod
    def _berth_dict(b) -> dict:
        return {
            "id": b.id,
            "name": b.name,
            "length_m": b.length_m,
            "depth_m": b.depth_m,
            "crane_count": b.crane_count,
            "yard_zone": b.yard_zone,
            "position_x": b.position_x,
            "position_y": b.position_y,
        }

    @staticmethod
    def _assignment_dict(a: Assignment, berth_name: Optional[str]) -> dict:
        return {
            "voyage_id": a.voyage_id,
            "berth_id": a.berth_id,
            "berth_name": berth_name,
            "etb": a.etb,
            "etd": a.etd,
            "wait_min": a.wait_min,
            "locked": a.locked,
            "source": a.source,
        }

    @staticmethod
    def _build_timeline(voyage, assignment: Optional[Assignment], berth_name: Optional[str]) -> list:
        items = [{"stage": "预计到港", "time": voyage.eta, "detail": voyage.vessel_name}]
        if assignment and assignment.etb:
            items.append({"stage": "靠泊", "time": assignment.etb, "detail": berth_name or "待定泊位"})
        if assignment and assignment.etd:
            items.append(
                {
                    "stage": "离泊",
                    "time": assignment.etd,
                    "detail": f"作业约 {voyage.service_hours} 小时",
                }
            )
        return items
