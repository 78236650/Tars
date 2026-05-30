from __future__ import annotations

from typing import Dict, List, Tuple

from .models import Assignment, Berth, Voyage


class ShipPlanAgent:
    """船舶计划 Agent（v1 规则实现，无 LLM 依赖）。"""

    def preprocess(self, berths: List[Berth], voyages: List[Voyage]) -> dict:
        feasible: Dict[str, List[str]] = {}
        warnings: List[str] = []
        for v in voyages:
            ids = [b.id for b in berths if v.draft_m <= b.depth_m and v.length_m <= b.length_m]
            feasible[v.id] = ids
            if not ids:
                warnings.append(f"{v.vessel_name} 无满足吃水/船长的泊位")
            elif v.priority >= 2:
                warnings.append(f"{v.vessel_name} 为 VIP 优先船，已提升排序")
        return {"feasible_berths": feasible, "warnings": warnings}

    def postprocess(
        self,
        berths: List[Berth],
        voyages: List[Voyage],
        assignments: List[Assignment],
        warnings: List[str],
    ) -> Tuple[str, Dict[str, str], List[str]]:
        berths_by_id = {b.id: b for b in berths}
        voyages_by_id = {v.id: v for v in voyages}
        notes: Dict[str, str] = {}
        total_wait = 0.0
        assigned = 0

        for a in assignments:
            v = voyages_by_id.get(a.voyage_id)
            if not v:
                continue
            if a.berth_id and a.etb:
                b = berths_by_id.get(a.berth_id)
                bname = b.name if b else a.berth_id
                notes[a.voyage_id] = (
                    f"{v.vessel_name} 建议 {a.etb[:16]} 靠 {bname}，"
                    f"等待 {a.wait_min:.0f} 分钟"
                )
                total_wait += a.wait_min
                assigned += 1
            else:
                notes[a.voyage_id] = f"{v.vessel_name} 未能自动分配泊位，请人工处理"

        summary = (
            f"48小时窗口共 {len(voyages)} 艘船，已排 {assigned} 艘，"
            f"总等待约 {total_wait:.0f} 分钟。"
        )
        if warnings:
            summary += f" 注意 {len(warnings)} 条告警。"
        return summary, notes, warnings

    def alternatives(self, voyage: Voyage, berths: List[Berth], chosen_id: str | None) -> List[str]:
        alts = []
        for b in berths:
            if b.id == chosen_id:
                continue
            if voyage.draft_m <= b.depth_m and voyage.length_m <= b.length_m:
                alts.append(b.name)
        return alts[:3]
