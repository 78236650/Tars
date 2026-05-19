"""Rule-based table role classification (fact/dimension/config/log)."""
from __future__ import annotations

import re
from typing import Any, Dict, List


class RoleClassifier:
    LOG_PATTERN = re.compile(r"(log|event|audit|trace)", re.I)

    def classify_tables(
        self,
        schema: Dict[str, Any],
        table_stats: Dict[str, Any],
        core_top_n: int = 20,
    ) -> Dict[str, Any]:
        tables = schema.get("tables") or {}
        ranked: List[tuple] = []
        for name, tst in table_stats.items():
            row_est = 0
            if hasattr(tst, "row_estimate"):
                row_est = tst.row_estimate or 0
            elif isinstance(tst, dict):
                row_est = tst.get("row_estimate") or 0
            ranked.append((name, row_est))
        ranked.sort(key=lambda x: x[1], reverse=True)

        roles: Dict[str, str] = {}
        tiers = {"core": [], "reference": [], "skipped": []}

        for name, row_est in ranked:
            tdef = tables.get(name) or {}
            role = self._classify_one(name, tdef, row_est)
            roles[name] = role
            if name in [r[0] for r in ranked[:core_top_n]]:
                tiers["core"].append(name)
            elif role in ("config", "bridge"):
                tiers["reference"].append(name)

        return {"table_roles": roles, "table_tiers": tiers}

    def _classify_one(self, name: str, tdef: Dict[str, Any], row_est: int) -> str:
        if self.LOG_PATTERN.search(name):
            return "log"
        cols = tdef.get("columns") or []
        col_names = [c.get("name", "").lower() for c in cols]
        has_time = any("time" in c or "date" in c or c.endswith("_at") for c in col_names)
        fk_count = len(tdef.get("foreign_keys") or [])
        if row_est and row_est < 500 and not has_time:
            return "config"
        if fk_count >= 2 and len(cols) <= 6:
            return "bridge"
        if row_est and row_est > 10000 and has_time:
            return "fact"
        if has_time or fk_count:
            return "dimension"
        return "reference"
