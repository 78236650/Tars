#!/usr/bin/env python3
"""Functional smoke tests for memory tree APIs (runs against tars.main app)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from tars.main import app


def main() -> int:
    client = TestClient(app)
    failed = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal failed
        if cond:
            print(f"  OK  {name}")
        else:
            print(f"  FAIL {name} {detail}")
            failed += 1

    print("Memory tree functional checks")
    r = client.get("/api/memory/tree", params={"view": "entity"})
    check("GET /tree entity 200", r.status_code == 200)
    body = r.json()
    check("tree has nodes", len(body.get("nodes", [])) > 0)
    check("tree stats", body["stats"]["entity_count"] >= 1)

    r = client.get("/api/memory/tree", params={"view": "provenance"})
    check("GET /tree provenance 200", r.status_code == 200)

    r = client.get("/api/memory/tree/graph")
    check("GET /tree/graph 200", r.status_code == 200)
    if r.status_code == 200:
        g = r.json()
        check("graph nodes", g["stats"]["node_count"] >= 1)
        check("graph edges or empty ok", g["stats"]["edge_count"] >= 0)

    r = client.get("/api/memory/tree/search", params={"q": "TREE_DEMO"})
    check("GET /tree/search 200", r.status_code == 200)
    if r.status_code == 200:
        check("search demo hit", len(r.json().get("items", [])) >= 1, str(r.json()))

    entities = []
    for n in body.get("nodes", []):
        if n.get("kind") == "entity":
            entities.append(n["id"])
        for c in n.get("children") or []:
            if c.get("kind") == "entity":
                entities.append(c["id"])
            for cc in c.get("children") or []:
                if cc.get("kind") == "entity":
                    entities.append(cc["id"])
    if entities:
        eid = entities[0]
        r = client.get("/api/memory/tree/relations", params={"entity_id": eid})
        check(f"GET /tree/relations ({eid[:20]}…)", r.status_code == 200)
    else:
        check("skip relations (no entity)", True)

    print(f"\n{'All passed' if not failed else f'{failed} failed'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
