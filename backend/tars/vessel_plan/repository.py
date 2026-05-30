from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .models import Assignment, Berth, Voyage


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


class VesselPlanRepository:
    def __init__(self, db, tenant_id: str = "default"):
        self.db = db
        self.tenant_id = tenant_id

    def count_berths(self) -> int:
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS cnt FROM vp_berths WHERE tenant_id = ?",
            (self.tenant_id,),
        )
        return int(row["cnt"]) if row else 0

    def list_berths(self) -> List[Berth]:
        rows = self.db.fetch_all(
            "SELECT id, name, length_m, depth_m, crane_count, yard_zone, position_x, position_y "
            "FROM vp_berths WHERE tenant_id = ? ORDER BY position_x",
            (self.tenant_id,),
        )
        return [
            Berth(
                id=r["id"],
                name=r["name"],
                length_m=float(r["length_m"]),
                depth_m=float(r["depth_m"]),
                crane_count=int(r["crane_count"]),
                yard_zone=r["yard_zone"],
                position_x=float(r["position_x"]),
                position_y=float(r["position_y"]),
            )
            for r in rows
        ]

    def upsert_berth(self, b: Berth) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO vp_berths "
            "(id, tenant_id, name, length_m, depth_m, crane_count, yard_zone, position_x, position_y) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                b.id,
                self.tenant_id,
                b.name,
                b.length_m,
                b.depth_m,
                b.crane_count,
                b.yard_zone,
                b.position_x,
                b.position_y,
            ),
        )

    def horizon_voyages(self, hours: int = 48) -> List[Voyage]:
        now = datetime.now(timezone(timedelta(hours=8)))
        start = now.isoformat()
        end = (now + timedelta(hours=hours)).isoformat()
        rows = self.db.fetch_all(
            """
            SELECT v.id, v.vessel_id, s.name AS vessel_name, v.eta, v.etd_est,
                   v.cargo_teu, v.target_yard_zone, v.service_hours, v.status,
                   s.length_m, s.draft_m, s.priority
            FROM vp_voyages v
            JOIN vp_vessels s ON s.id = v.vessel_id AND s.tenant_id = v.tenant_id
            WHERE v.tenant_id = ? AND v.status = 'pending' AND v.eta >= ? AND v.eta <= ?
            ORDER BY v.eta
            """,
            (self.tenant_id, start, end),
        )
        return [
            Voyage(
                id=r["id"],
                vessel_id=r["vessel_id"],
                vessel_name=r["vessel_name"],
                eta=r["eta"],
                etd_est=r.get("etd_est"),
                cargo_teu=int(r["cargo_teu"]),
                target_yard_zone=r["target_yard_zone"],
                service_hours=float(r["service_hours"]),
                status=r["status"],
                length_m=float(r["length_m"]),
                draft_m=float(r["draft_m"]),
                priority=int(r["priority"]),
            )
            for r in rows
        ]

    def get_voyage(self, voyage_id: str) -> Optional[Voyage]:
        row = self.db.fetch_one(
            """
            SELECT v.id, v.vessel_id, s.name AS vessel_name, v.eta, v.etd_est,
                   v.cargo_teu, v.target_yard_zone, v.service_hours, v.status,
                   s.length_m, s.draft_m, s.priority
            FROM vp_voyages v
            JOIN vp_vessels s ON s.id = v.vessel_id AND s.tenant_id = v.tenant_id
            WHERE v.tenant_id = ? AND v.id = ?
            """,
            (self.tenant_id, voyage_id),
        )
        if not row:
            return None
        return Voyage(
            id=row["id"],
            vessel_id=row["vessel_id"],
            vessel_name=row["vessel_name"],
            eta=row["eta"],
            etd_est=row.get("etd_est"),
            cargo_teu=int(row["cargo_teu"]),
            target_yard_zone=row["target_yard_zone"],
            service_hours=float(row["service_hours"]),
            status=row["status"],
            length_m=float(row["length_m"]),
            draft_m=float(row["draft_m"]),
            priority=int(row["priority"]),
        )

    def get_assignment_map(self) -> Dict[str, Assignment]:
        rows = self.db.fetch_all(
            "SELECT voyage_id, berth_id, etb, etd, wait_min, yard_penalty, score, source, locked "
            "FROM vp_assignments WHERE tenant_id = ?",
            (self.tenant_id,),
        )
        out: Dict[str, Assignment] = {}
        for r in rows:
            out[r["voyage_id"]] = Assignment(
                voyage_id=r["voyage_id"],
                berth_id=r.get("berth_id"),
                etb=r.get("etb"),
                etd=r.get("etd"),
                wait_min=float(r["wait_min"]),
                yard_penalty=float(r["yard_penalty"]),
                score=float(r["score"]),
                source=r["source"],
                locked=bool(r["locked"]),
            )
        return out

    def save_assignments(self, items: List[Assignment]) -> None:
        for a in items:
            self.db.execute(
                "INSERT OR REPLACE INTO vp_assignments "
                "(voyage_id, tenant_id, berth_id, etb, etd, wait_min, yard_penalty, score, source, locked, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    a.voyage_id,
                    self.tenant_id,
                    a.berth_id,
                    a.etb,
                    a.etd,
                    a.wait_min,
                    a.yard_penalty,
                    a.score,
                    a.source,
                    int(a.locked),
                    _now_iso(),
                ),
            )

    def clear_unlocked_assignments(self) -> None:
        self.db.execute(
            "DELETE FROM vp_assignments WHERE tenant_id = ? AND locked = 0",
            (self.tenant_id,),
        )

    def mark_voyage_dispatched(self, voyage_id: str) -> None:
        self.db.execute(
            "UPDATE vp_voyages SET status = 'dispatched' WHERE tenant_id = ? AND id = ?",
            (self.tenant_id, voyage_id),
        )

    def save_plan_run(
        self,
        run_id: str,
        horizon_hours: int,
        objective: str,
        constraints: dict,
        total_wait: float,
        summary: str,
    ) -> None:
        self.db.execute(
            "INSERT INTO vp_plan_runs (id, tenant_id, horizon_hours, objective, constraints_json, "
            "total_wait_min, status, agent_summary, created_at) VALUES (?, ?, ?, ?, ?, ?, 'done', ?, ?)",
            (
                run_id,
                self.tenant_id,
                horizon_hours,
                objective,
                json.dumps(constraints, ensure_ascii=False),
                total_wait,
                summary,
                _now_iso(),
            ),
        )

    def clear_demo_data(self) -> None:
        for table in ("vp_assignments", "vp_plan_runs", "vp_voyages", "vp_vessels", "vp_berths"):
            self.db.execute(f"DELETE FROM {table} WHERE tenant_id = ?", (self.tenant_id,))
