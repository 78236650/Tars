#!/usr/bin/env python3
"""InsightForge INS-1.0.0 functional smoke test against running TARS API."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("TARS_API_BASE", "http://127.0.0.1:8000")
TENANT = os.environ.get("TARS_TENANT_ID", "4a863625-6bc1-472d-8ce1-c83511c95e49")
DS_DEMO = os.environ.get("TARS_INSIGHT_DEMO_DS", "bd565063-1d8b-48bb-94e8-35da70a3c53c")


def req(method: str, path: str, body: dict | None = None) -> tuple[int, dict | list | str]:
    url = f"{BASE}{path}"
    data = None
    headers = {"X-Tenant-ID": TENANT, "Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return e.code, payload


def ok(cond: bool, msg: str) -> None:
    print(("PASS" if cond else "FAIL") + f"  {msg}")
    if not cond:
        raise SystemExit(1)


def main() -> None:
    print(f"API base: {BASE}  tenant: {TENANT[:8]}…")
    checks: list[tuple[str, bool]] = []

    code, mods = req("GET", "/api/modules")
    mod_names = [m["name"] for m in mods] if isinstance(mods, list) else []
    checks.append(("modules.insight", code == 200 and "insight" in mod_names))

    code, ver = req("GET", "/api/insight/version")
    checks.append(("insight.version", code == 200 and ver.get("version") == "INS-1.0.0"))

    code, ds_res = req("GET", "/api/datasources/")
    dss = ds_res.get("datasources", []) if isinstance(ds_res, dict) else []
    checks.append(("bi.datasources", code == 200 and len(dss) >= 1))

    demo = next((d for d in dss if d.get("id") == DS_DEMO or "鉴数Demo" in (d.get("name") or "")), None)
    ds_id = demo["id"] if demo else (dss[0]["id"] if dss else DS_DEMO)
    checks.append(("demo.datasource", demo is not None or len(dss) > 0))

    code, runs = req("GET", f"/api/insight/datasources/{ds_id}/profile/runs")
    run_list = runs.get("runs", []) if isinstance(runs, dict) else []
    checks.append(("insight.profile.runs", code == 200))

    code, brief = req("GET", f"/api/insight/datasources/{ds_id}/brief")
    if code == 404:
        code2, one = req("GET", f"/api/datasources/{ds_id}")
        ann = len((one.get("schema_annotations") or {}) if isinstance(one, dict) else {})
        checks.append(("insight.brief (fallback via datasource)", code2 == 200 and ann >= 1))
    else:
        ann = brief.get("datasource", {}).get("annotation_count", 0)
        checks.append(("insight.brief", code == 200 and ann >= 1))

    completed = [r for r in run_list if r.get("status") == "completed"]
    checks.append(("profile.has_completed", len(completed) >= 1))

    if completed:
        run_id = completed[0]["id"]
        code, run = req("GET", f"/api/insight/profile/runs/{run_id}")
        snap = run.get("insight_snapshot") or {}
        tables = snap.get("tables") or {}
        checks.append(("profile.snapshot.tables", code == 200 and len(tables) >= 1))

    for name, passed in checks:
        ok(passed, name)

    print("\nAll InsightForge functional checks passed.")


if __name__ == "__main__":
    main()
