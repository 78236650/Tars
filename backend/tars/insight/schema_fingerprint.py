"""Schema fingerprinting for InsightForge incremental profiling."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def fingerprint_table(tdef: dict) -> str:
    """Stable hash for table structure (columns + primary key)."""
    cols = sorted(
        (c.get("name", ""), str(c.get("type", "")), c.get("nullable"))
        for c in (tdef.get("columns") or [])
    )
    pk = tuple(sorted(tdef.get("primary_key") or []))
    payload = json.dumps({"cols": cols, "pk": pk}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def fingerprint_schema(schema: Dict[str, Any]) -> Dict[str, str]:
    """Return table name -> fingerprint for all tables in schema."""
    tables = schema.get("tables") or {}
    return {name: fingerprint_table(tdef) for name, tdef in tables.items()}


def fingerprints_equal(fp1: Dict[str, str], fp2: Dict[str, str], table: str) -> bool:
    return fp1.get(table) == fp2.get(table)
