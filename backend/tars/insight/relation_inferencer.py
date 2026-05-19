"""Foreign key and heuristic relation inference."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Set


@dataclass
class RelationEdge:
    from_ref: str
    to_ref: str
    type: str
    confidence: float
    evidence: str


class RelationInferencer:
    def __init__(self, max_pairs: int = 200):
        self.max_pairs = max_pairs

    def infer(
        self,
        schema: Dict[str, Any],
        table_stats: Dict[str, Any],
        core_tables: List[str],
    ) -> List[RelationEdge]:
        edges: List[RelationEdge] = []
        seen: Set[str] = set()
        tables = schema.get("tables") or {}

        for table, tdef in tables.items():
            for fk in tdef.get("foreign_keys") or []:
                col = fk.get("column", "")
                rt = fk.get("referred_table", "")
                rc = fk.get("referred_column", "id")
                if not col or not rt:
                    continue
                from_ref = f"{table}.{col}"
                to_ref = f"{rt}.{rc}"
                key = f"{from_ref}->{to_ref}"
                if key in seen:
                    continue
                seen.add(key)
                edges.append(
                    RelationEdge(
                        from_ref=from_ref,
                        to_ref=to_ref,
                        type="fk_declared",
                        confidence=1.0,
                        evidence="declared foreign key",
                    )
                )

        id_columns_by_table: Dict[str, List[str]] = {}
        for table, tdef in tables.items():
            pks = tdef.get("primary_key") or []
            cols = [c.get("name") for c in tdef.get("columns") or []]
            id_cols = [c for c in cols if c and (c in pks or c.lower() == "id")]
            id_columns_by_table[table] = id_cols or (["id"] if "id" in (cols or []) else [])

        pairs = 0
        for table in core_tables:
            tdef = tables.get(table) or {}
            for col in [c.get("name") for c in tdef.get("columns") or []]:
                if pairs >= self.max_pairs:
                    break
                if not col or not col.lower().endswith("_id"):
                    continue
                guess_table = col[:-3]
                if guess_table in tables:
                    targets = id_columns_by_table.get(guess_table) or ["id"]
                    to_ref = f"{guess_table}.{targets[0]}"
                    from_ref = f"{table}.{col}"
                    key = f"{from_ref}->{to_ref}"
                    if key in seen:
                        continue
                    seen.add(key)
                    pairs += 1
                    edges.append(
                        RelationEdge(
                            from_ref=from_ref,
                            to_ref=to_ref,
                            type="naming_guess",
                            confidence=0.6,
                            evidence=f"column name pattern {col}",
                        )
                    )

        return edges
