# 船舶进出港计划（Agent + OR）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在作业调度 `/orchestration` 增加「进出港计划」Tab，基于内置拟真数据实现 48h 泊位计划、Agent↔OR 协同求解、泊位甘特图/平面图可视化，并支持微调、重算与下发至现有 orchestration dispatch。

**Architecture:** 新增 `backend/tars/vessel_plan/` 包（seed、repository、BerthScheduler、ShipPlanAgent、VesselPlanService）+ `vessel_plan_routes.py`；前端 `components/vessel-plan/` + `OrchestrationView` Tab；下发复用 `MultiAgentOrchestrator.orchestrate()`。

**Tech Stack:** Python 3 / FastAPI / SQLite（现有 Database）/ Vue 3 + SVG 自绘甘特与泊位图 / 现有 i18n + orchestration API

**Spec:** [2026-05-30-vessel-plan-or-design.md](../specs/2026-05-30-vessel-plan-or-design.md)

---

## File Map

| 路径 | 职责 |
|------|------|
| `backend/tars/database/connection.py` | 新增 5 张 `vp_*` 表 |
| `backend/tars/vessel_plan/models.py` | Berth/Voyage/Assignment dataclass |
| `backend/tars/vessel_plan/seed.py` | 元洪 Demo 6 泊位 + 12 航次 |
| `backend/tars/vessel_plan/repository.py` | CRUD + horizon 查询 |
| `backend/tars/vessel_plan/berth_scheduler.py` | OR 求解器 |
| `backend/tars/vessel_plan/ship_plan_agent.py` | 约束预处理 + 结果后处理 |
| `backend/tars/vessel_plan/service.py` | optimize / patch / recompute / adopt |
| `backend/tars/api/vessel_plan_routes.py` | REST API |
| `backend/tars/main.py` | 注册 router（orchestration 模块内） |
| `backend/tests/test_berth_scheduler.py` | 求解器单测 |
| `backend/tests/test_vessel_plan_api.py` | API 单测 |
| `backend/tests/test_vessel_plan_e2e.py` | 全链路 |
| `frontend/src/types/vessel-plan.ts` | TS 类型 |
| `frontend/src/api/index.ts` | `vesselPlanApi` |
| `frontend/src/views/OrchestrationView.vue` | Tab 容器 |
| `frontend/src/components/vessel-plan/*.vue` | 甘特/平面图/抽屉等 |
| `frontend/src/i18n/index.ts` | 中文文案 |

---

### Task 1: 数据库表 `vp_*`

**Files:**
- Modify: `backend/tars/database/connection.py`（在 `agent_collaboration_ctx` 建表之后追加）
- Test: `backend/tests/test_vessel_plan_repository.py`（Task 2 创建，此处仅建表）

- [ ] **Step 1: 在 `_init_schema` 追加 DDL**

在 `agent_collaboration_ctx` 块之后、`interaction_stats` 之前插入：

```python
        # v4.5.0 船舶进出港计划（拟真）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vp_berths (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                name TEXT NOT NULL,
                length_m REAL NOT NULL,
                depth_m REAL NOT NULL,
                crane_count INTEGER NOT NULL DEFAULT 2,
                yard_zone TEXT NOT NULL DEFAULT 'A',
                position_x REAL NOT NULL DEFAULT 0,
                position_y REAL NOT NULL DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vp_vessels (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                name TEXT NOT NULL,
                imo TEXT,
                length_m REAL NOT NULL,
                draft_m REAL NOT NULL,
                priority INTEGER NOT NULL DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vp_voyages (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                vessel_id TEXT NOT NULL,
                eta TEXT NOT NULL,
                etd_est TEXT,
                cargo_teu INTEGER NOT NULL DEFAULT 0,
                target_yard_zone TEXT NOT NULL DEFAULT 'A',
                service_hours REAL NOT NULL DEFAULT 8,
                status TEXT NOT NULL DEFAULT 'pending'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vp_assignments (
                voyage_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                berth_id TEXT,
                etb TEXT,
                etd TEXT,
                wait_min REAL NOT NULL DEFAULT 0,
                yard_penalty REAL NOT NULL DEFAULT 0,
                score REAL NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'or',
                locked INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vp_plan_runs (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                horizon_hours INTEGER NOT NULL DEFAULT 48,
                objective TEXT NOT NULL,
                constraints_json TEXT NOT NULL DEFAULT '{}',
                total_wait_min REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'done',
                agent_summary TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vp_voyages_eta ON vp_voyages(tenant_id, eta)")
```

- [ ] **Step 2: 验证表创建**

Run: `cd backend && python3 -c "from tars.database.connection import Database; Database(); print('ok')"`
Expected: `ok`（无异常）

- [ ] **Step 3: Commit**

```bash
git add backend/tars/database/connection.py
git commit -m "feat(vessel-plan): add vp_* tables for demo port planning"
```

---

### Task 2: Models + Repository

**Files:**
- Create: `backend/tars/vessel_plan/__init__.py`
- Create: `backend/tars/vessel_plan/models.py`
- Create: `backend/tars/vessel_plan/repository.py`
- Create: `backend/tests/test_vessel_plan_repository.py`

- [ ] **Step 1: Write failing repository test**

```python
# backend/tests/test_vessel_plan_repository.py
from tars.database.connection import Database
from tars.vessel_plan.repository import VesselPlanRepository


def test_list_berths_empty():
    db = Database(":memory:")
    repo = VesselPlanRepository(db, tenant_id="default")
    assert repo.list_berths() == []
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd backend && python3 -m pytest tests/test_vessel_plan_repository.py::test_list_berths_empty -v`
Expected: FAIL `ModuleNotFoundError: vessel_plan`

- [ ] **Step 3: Implement models.py**

```python
# backend/tars/vessel_plan/models.py
from dataclasses import dataclass
from typing import Optional


@dataclass
class Berth:
    id: str
    name: str
    length_m: float
    depth_m: float
    crane_count: int
    yard_zone: str
    position_x: float
    position_y: float


@dataclass
class Vessel:
    id: str
    name: str
    imo: str
    length_m: float
    draft_m: float
    priority: int


@dataclass
class Voyage:
    id: str
    vessel_id: str
    vessel_name: str
    eta: str
    etd_est: Optional[str]
    cargo_teu: int
    target_yard_zone: str
    service_hours: float
    status: str
    length_m: float
    draft_m: float
    priority: int


@dataclass
class Assignment:
    voyage_id: str
    berth_id: Optional[str]
    etb: Optional[str]
    etd: Optional[str]
    wait_min: float
    yard_penalty: float
    score: float
    source: str
    locked: bool
```

- [ ] **Step 4: Implement repository.py（最小 list_berths + upsert_berth）**

```python
# backend/tars/vessel_plan/repository.py
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from ..database.connection import Database
from .models import Assignment, Berth, Vessel, Voyage


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


class VesselPlanRepository:
    def __init__(self, db: Database, tenant_id: str = "default"):
        self.db = db
        self.tenant_id = tenant_id

    def list_berths(self) -> List[Berth]:
        rows = self.db.fetch_all(
            "SELECT id, name, length_m, depth_m, crane_count, yard_zone, position_x, position_y "
            "FROM vp_berths WHERE tenant_id = ? ORDER BY name",
            (self.tenant_id,),
        )
        return [Berth(*r) for r in rows]

    def upsert_berth(self, b: Berth) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO vp_berths "
            "(id, tenant_id, name, length_m, depth_m, crane_count, yard_zone, position_x, position_y) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (b.id, self.tenant_id, b.name, b.length_m, b.depth_m, b.crane_count,
             b.yard_zone, b.position_x, b.position_y),
        )

    def horizon_voyages(self, hours: int = 48) -> List[Voyage]:
        now = datetime.now(timezone(timedelta(hours=8)))
        end = (now + timedelta(hours=hours)).isoformat()
        start = now.isoformat()
        rows = self.db.fetch_all(
            """
            SELECT v.id, v.vessel_id, s.name, v.eta, v.etd_est, v.cargo_teu,
                   v.target_yard_zone, v.service_hours, v.status,
                   s.length_m, s.draft_m, s.priority
            FROM vp_voyages v
            JOIN vp_vessels s ON s.id = v.vessel_id AND s.tenant_id = v.tenant_id
            WHERE v.tenant_id = ? AND v.status = 'pending' AND v.eta >= ? AND v.eta <= ?
            ORDER BY v.eta
            """,
            (self.tenant_id, start, end),
        )
        return [Voyage(
            id=r[0], vessel_id=r[1], vessel_name=r[2], eta=r[3], etd_est=r[4],
            cargo_teu=r[5], target_yard_zone=r[6], service_hours=r[7], status=r[8],
            length_m=r[9], draft_m=r[10], priority=r[11],
        ) for r in rows]

    def get_assignment_map(self) -> dict[str, Assignment]:
        rows = self.db.fetch_all(
            "SELECT voyage_id, berth_id, etb, etd, wait_min, yard_penalty, score, source, locked "
            "FROM vp_assignments WHERE tenant_id = ?",
            (self.tenant_id,),
        )
        out = {}
        for r in rows:
            out[r[0]] = Assignment(
                voyage_id=r[0], berth_id=r[1], etb=r[2], etd=r[3],
                wait_min=r[4], yard_penalty=r[5], score=r[6], source=r[7], locked=bool(r[8]),
            )
        return out

    def save_assignments(self, items: List[Assignment]) -> None:
        for a in items:
            self.db.execute(
                "INSERT OR REPLACE INTO vp_assignments "
                "(voyage_id, tenant_id, berth_id, etb, etd, wait_min, yard_penalty, score, source, locked, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (a.voyage_id, self.tenant_id, a.berth_id, a.etb, a.etd,
                 a.wait_min, a.yard_penalty, a.score, a.source, int(a.locked), _now_iso()),
            )

    def clear_assignments(self) -> None:
        self.db.execute("DELETE FROM vp_assignments WHERE tenant_id = ?", (self.tenant_id,))

    def save_plan_run(self, run_id: str, horizon_hours: int, objective: str,
                      constraints: dict, total_wait: float, summary: str) -> None:
        self.db.execute(
            "INSERT INTO vp_plan_runs (id, tenant_id, horizon_hours, objective, constraints_json, "
            "total_wait_min, status, agent_summary, created_at) VALUES (?, ?, ?, ?, ?, ?, 'done', ?, ?)",
            (run_id, self.tenant_id, horizon_hours, objective, json.dumps(constraints, ensure_ascii=False),
             total_wait, summary, _now_iso()),
        )
```

- [ ] **Step 5: Run test — expect PASS**

Run: `cd backend && python3 -m pytest tests/test_vessel_plan_repository.py::test_list_berths_empty -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/tars/vessel_plan backend/tests/test_vessel_plan_repository.py
git commit -m "feat(vessel-plan): add models and repository"
```

---

### Task 3: Demo Seed 数据

**Files:**
- Create: `backend/tars/vessel_plan/seed.py`
- Modify: `backend/tests/test_vessel_plan_repository.py`

- [ ] **Step 1: Write failing seed test**

```python
def test_seed_demo_populates_berths_and_voyages():
    db = Database(":memory:")
    from tars.vessel_plan.seed import seed_demo_port
    seed_demo_port(db, tenant_id="default")
    repo = VesselPlanRepository(db, tenant_id="default")
    berths = repo.list_berths()
    voyages = repo.horizon_voyages(hours=48)
    assert len(berths) == 6
    assert len(voyages) >= 8
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && python3 -m pytest tests/test_vessel_plan_repository.py::test_seed_demo_populates_berths_and_voyages -v`
Expected: FAIL

- [ ] **Step 3: Implement seed.py**

6 个泊位（1#–6#，`position_x` 0/120/240…，`yard_zone` A/B/C），12 条船（COSCO/MAERSK 等），ETA 分布在未来 6–46 小时内，`service_hours` 6–12。

```python
# backend/tars/vessel_plan/seed.py
from datetime import datetime, timedelta, timezone
import uuid

from ..database.connection import Database
from .models import Berth, Vessel
from .repository import VesselPlanRepository


def seed_demo_port(db: Database, tenant_id: str = "default") -> dict:
    repo = VesselPlanRepository(db, tenant_id=tenant_id)
    repo.db.execute("DELETE FROM vp_assignments WHERE tenant_id = ?", (tenant_id,))
    repo.db.execute("DELETE FROM vp_voyages WHERE tenant_id = ?", (tenant_id,))
    repo.db.execute("DELETE FROM vp_vessels WHERE tenant_id = ?", (tenant_id,))
    repo.db.execute("DELETE FROM vp_berths WHERE tenant_id = ?", (tenant_id,))

    berths = [
        Berth("b1", "1号泊位", 350, 15.5, 3, "A", 0, 0),
        Berth("b2", "2号泊位", 320, 14.0, 2, "A", 120, 0),
        Berth("b3", "3号泊位", 400, 16.0, 4, "B", 240, 0),
        Berth("b4", "4号泊位", 280, 13.5, 2, "B", 360, 0),
        Berth("b5", "5号泊位", 300, 14.5, 2, "C", 480, 0),
        Berth("b6", "6号泊位", 260, 12.5, 1, "C", 600, 0),
    ]
    for b in berths:
        repo.upsert_berth(b)

    vessels = [
        ("COSCO123", "COSCO123", "UN1234567", 366, 13.2, 2),
        ("MAERSK88", "MAERSK88", "UN2345678", 340, 12.8, 1),
        ("EVER101", "EVER GIVEN", "UN3456789", 400, 15.0, 0),
        ("HLC456", "HLC456", "UN4567890", 295, 11.5, 0),
        ("OOCL789", "OOCL789", "UN5678901", 320, 12.0, 1),
        ("YML222", "YML222", "UN6789012", 280, 10.5, 0),
        ("PIL333", "PIL333", "UN7890123", 260, 10.0, 0),
        ("WHL444", "WHL444", "UN8901234", 310, 11.8, 0),
        ("SITC555", "SITC555", "UN9012345", 240, 9.5, 0),
        ("ZIM666", "ZIM666", "UN0123456", 330, 12.5, 1),
        ("ONE777", "ONE777", "UN1122334", 350, 13.0, 2),
        ("CMA888", "CMA888", "UN2233445", 300, 11.0, 0),
    ]
    now = datetime.now(timezone(timedelta(hours=8)))
    for i, (vid, name, imo, loa, draft, pri) in enumerate(vessels):
        repo.db.execute(
            "INSERT INTO vp_vessels (id, tenant_id, name, imo, length_m, draft_m, priority) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (vid, tenant_id, name, imo, loa, draft, pri),
        )
        eta = (now + timedelta(hours=4 + i * 3.5)).isoformat()
        repo.db.execute(
            "INSERT INTO vp_voyages (id, tenant_id, vessel_id, eta, etd_est, cargo_teu, target_yard_zone, service_hours, status) "
            "VALUES (?, ?, ?, ?, NULL, ?, ?, ?, 'pending')",
            (f"v{i+1}", tenant_id, vid, eta, 600 + i * 50, ["A", "A", "B", "B", "C", "C"][i % 6], 8 + (i % 3) * 2),
        )
    return {"berths": 6, "voyages": 12}
```

- [ ] **Step 4: Run test — PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/tars/vessel_plan/seed.py backend/tests/test_vessel_plan_repository.py
git commit -m "feat(vessel-plan): add demo port seed data"
```

---

### Task 4: BerthScheduler（OR 求解器）TDD

**Files:**
- Create: `backend/tars/vessel_plan/berth_scheduler.py`
- Create: `backend/tests/test_berth_scheduler.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_berth_scheduler.py
from datetime import datetime, timedelta, timezone
from tars.vessel_plan.berth_scheduler import BerthScheduler, ScheduleInput
from tars.vessel_plan.models import Berth, Voyage


def _voyage(vid, eta_h, loa=300, draft=12, zone="A", pri=0, hours=8):
    tz = timezone(timedelta(hours=8))
    eta = datetime(2026, 6, 1, eta_h, 0, tzinfo=tz).isoformat()
    return Voyage(vid, vid, vid, eta, None, 800, zone, hours, "pending", loa, draft, pri)


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
```

- [ ] **Step 2: Run — FAIL**

Run: `cd backend && python3 -m pytest tests/test_berth_scheduler.py -v`
Expected: FAIL

- [ ] **Step 3: Implement berth_scheduler.py**

核心逻辑：
- `ScheduleInput(berths, voyages, locked: dict[voyage_id, Assignment])`
- 按 `(priority desc, eta asc)` 排序
- 对每个 voyage，在可行 berth 中选 `wait_min + yard_lambda * zone_mismatch` 最小
- `etb = max(eta, berth_free_time)`；`etd = etb + service_hours`
- 返回 `ScheduleResult(assignments, total_wait_min, warnings)`

- [ ] **Step 4: Run — PASS**

Run: `cd backend && python3 -m pytest tests/test_berth_scheduler.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/tars/vessel_plan/berth_scheduler.py backend/tests/test_berth_scheduler.py
git commit -m "feat(vessel-plan): add berth scheduler with overlap and draft checks"
```

---

### Task 5: ShipPlanAgent + VesselPlanService

**Files:**
- Create: `backend/tars/vessel_plan/ship_plan_agent.py`
- Create: `backend/tars/vessel_plan/service.py`
- Create: `backend/tests/test_vessel_plan_service.py`

- [ ] **Step 1: Write failing service test**

```python
def test_optimize_writes_assignments():
    db = Database(":memory:")
    seed_demo_port(db)
    from tars.vessel_plan.service import VesselPlanService
    svc = VesselPlanService(db, tenant_id="default")
    result = svc.optimize(horizon_hours=48)
    assert result["total_wait_min"] >= 0
    assert len(result["assignments"]) >= 8
    assert result["agent_summary"]
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement ship_plan_agent.py**

```python
class ShipPlanAgent:
    def preprocess(self, berths, voyages) -> dict:
        """返回 constraints: feasible_berths map, warnings."""
        ...

    def postprocess(self, berths, voyages, assignments, warnings) -> str:
        """返回中文摘要 + per-voyage notes list."""
        ...
```

规则实现（无 LLM 依赖 v1）：
- 前处理：`draft <= depth`, `length <= berth.length_m`；不可行写入 warnings
- 后处理：汇总等待、列出冲突/高风险（无泊位、等待>4h）

- [ ] **Step 4: Implement service.py**

```python
class VesselPlanService:
    def __init__(self, db, tenant_id="default"):
        self.repo = VesselPlanRepository(db, tenant_id)
        self.agent = ShipPlanAgent()
        self.scheduler = BerthScheduler(yard_lambda=0.15)

    def optimize(self, horizon_hours=48) -> dict:
        berths = self.repo.list_berths()
        voyages = self.repo.horizon_voyages(horizon_hours)
        constraints = self.agent.preprocess(berths, voyages)
        locked = {k: v for k, v in self.repo.get_assignment_map().items() if v.locked}
        result = self.scheduler.solve(ScheduleInput(berths, voyages, locked=locked, constraints=constraints))
        summary, notes = self.agent.postprocess(berths, voyages, result.assignments, result.warnings)
        self.repo.clear_assignments()
        self.repo.save_assignments(result.assignments)
        run_id = str(uuid.uuid4())
        self.repo.save_plan_run(run_id, horizon_hours, "min_wait+yard", constraints, result.total_wait_min, summary)
        return {"run_id": run_id, "assignments": [...], "total_wait_min": result.total_wait_min,
                "agent_summary": summary, "voyage_notes": notes, "warnings": result.warnings}

    def patch_assignment(self, voyage_id, berth_id=None, etb=None, etd=None, locked=False): ...
    def recompute(self, horizon_hours=48): ...  # 保留 locked
    def adopt(self, voyage_ids, session_id, orchestrator) -> list: ...  # 调 MultiAgentOrchestrator
```

- [ ] **Step 5: Run service test — PASS**

- [ ] **Step 6: Commit**

```bash
git add backend/tars/vessel_plan/ship_plan_agent.py backend/tars/vessel_plan/service.py backend/tests/test_vessel_plan_service.py
git commit -m "feat(vessel-plan): add ShipPlanAgent and VesselPlanService"
```

---

### Task 6: REST API + main.py 注册

**Files:**
- Create: `backend/tars/api/vessel_plan_routes.py`
- Modify: `backend/tars/main.py`
- Create: `backend/tests/test_vessel_plan_api.py`

- [ ] **Step 1: Write failing API test**

```python
from fastapi.testclient import TestClient
from tars.main import app

def test_horizon_requires_auth():
    client = TestClient(app)
    r = client.get("/api/vessel-plans/horizon")
    assert r.status_code in (401, 403)
```

- [ ] **Step 2: Implement vessel_plan_routes.py**

```python
router = APIRouter(prefix="/api/vessel-plans", tags=["vessel-plans"])

@router.get("/demo/status")
@router.post("/demo/reset")  # admin only
@router.get("/berths")
@router.get("/horizon")
@router.post("/optimize")
@router.patch("/assignments/{voyage_id}")
@router.post("/recompute")
@router.get("/voyages/{voyage_id}")
@router.post("/adopt")
```

`init_vessel_plan_api(db)` 存全局 `_db`；与 orchestration 相同 auth 模式。

- [ ] **Step 3: Wire main.py**

```python
from tars.api.vessel_plan_routes import router as vessel_plan_router, init_vessel_plan_api

if module_registry.is_enabled("orchestration"):
    app.include_router(vessel_plan_router)
    ...
    init_vessel_plan_api(db)
```

- [ ] **Step 4: Extend test with auth fixture（复用 test_orchestration_routes 模式）**

- [ ] **Step 5: Run API tests — PASS**

Run: `cd backend && python3 -m pytest tests/test_vessel_plan_api.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/tars/api/vessel_plan_routes.py backend/tars/main.py backend/tests/test_vessel_plan_api.py
git commit -m "feat(vessel-plan): add REST API and register with orchestration module"
```

---

### Task 7: E2E  adopt → orchestration

**Files:**
- Create: `backend/tests/test_vessel_plan_e2e.py`

- [ ] **Step 1: Write e2e test**

```python
def test_adopt_creates_orchestration_task():
    # seed → optimize → adopt first voyage → list orchestration tasks count >= 1
```

- [ ] **Step 2: Implement adopt in service**

`adopt` 构造 goal：
`f"安排 {vessel_name} {etb} 靠 {berth_name} 卸 {cargo_teu} 箱，堆场 {zone}"`
调用 `MultiAgentOrchestrator.orchestrate(session_id, goal)`；voyage status → `dispatched`

- [ ] **Step 3: Run — PASS**

Run: `cd backend && python3 -m pytest tests/test_vessel_plan_e2e.py -v`

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_vessel_plan_e2e.py backend/tars/vessel_plan/service.py
git commit -m "feat(vessel-plan): adopt dispatches to orchestration"
```

---

### Task 8: 前端类型与 API Client

**Files:**
- Create: `frontend/src/types/vessel-plan.ts`
- Modify: `frontend/src/types/index.ts`（re-export）
- Modify: `frontend/src/api/index.ts`

- [ ] **Step 1: 定义类型**

```typescript
export interface VpBerth {
  id: string
  name: string
  length_m: number
  depth_m: number
  crane_count: number
  yard_zone: string
  position_x: number
  position_y: number
}

export interface VpHorizonRow {
  voyage_id: string
  vessel_name: string
  eta: string
  etb: string | null
  etd: string | null
  berth_id: string | null
  berth_name: string | null
  wait_min: number
  target_yard_zone: string
  locked: boolean
  agent_note?: string
}

export interface VpHorizonResponse {
  berths: VpBerth[]
  rows: VpHorizonRow[]
  agent_summary: string
  total_wait_min: number
  warnings: string[]
}
```

- [ ] **Step 2: vesselPlanApi**

```typescript
export const vesselPlanApi = {
  demoStatus: () => api.get('/vessel-plans/demo/status'),
  resetDemo: () => api.post('/vessel-plans/demo/reset'),
  getBerths: () => api.get<VpBerth[]>('/vessel-plans/berths'),
  getHorizon: (hours = 48) => api.get<VpHorizonResponse>('/vessel-plans/horizon', { params: { hours } }),
  optimize: (hours = 48) => api.post('/vessel-plans/optimize', { horizon_hours: hours }),
  patchAssignment: (voyageId: string, body: object) => api.patch(`/vessel-plans/assignments/${voyageId}`, body),
  recompute: (hours = 48) => api.post('/vessel-plans/recompute', { horizon_hours: hours }),
  getVoyage: (id: string) => api.get(`/vessel-plans/voyages/${id}`),
  adopt: (voyageIds: string[], sessionId: string) =>
    api.post('/vessel-plans/adopt', { voyage_ids: voyageIds, session_id: sessionId }),
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/vessel-plan.ts frontend/src/types/index.ts frontend/src/api/index.ts
git commit -m "feat(vessel-plan): add frontend types and API client"
```

---

### Task 9: Orchestration Tab 容器

**Files:**
- Modify: `frontend/src/views/OrchestrationView.vue`
- Create: `frontend/src/components/vessel-plan/VesselPlanTab.vue`

- [ ] **Step 1: OrchestrationView 加 Tab**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import OrchestrationTaskView from '@/components/orchestration/OrchestrationTaskView.vue'
import VesselPlanTab from '@/components/vessel-plan/VesselPlanTab.vue'
import { useI18n } from '@/i18n'

const { t } = useI18n()
const tab = ref<'ops' | 'plan'>('ops')
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="flex gap-1 border-b border-border px-4 pt-3">
      <button ... @click="tab = 'ops'">{{ t('orchestration.tab.ops') }}</button>
      <button ... @click="tab = 'plan'">{{ t('orchestration.tab.plan') }}</button>
    </div>
    <OrchestrationTaskView v-if="tab === 'ops'" class="flex-1 min-h-0" />
    <VesselPlanTab v-else class="flex-1 min-h-0" />
  </div>
</template>
```

- [ ] **Step 2: VesselPlanTab 骨架**

布局：Toolbar + SummaryBar + 左甘特/右列表 + 底部 BerthLayoutMap

- [ ] **Step 3: i18n 键**

`orchestration.tab.ops` = 协同作业；`orchestration.tab.plan` = 进出港计划

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/OrchestrationView.vue frontend/src/components/vessel-plan/VesselPlanTab.vue frontend/src/i18n/index.ts
git commit -m "feat(vessel-plan): add orchestration tab shell"
```

---

### Task 10: BerthGanttChart（SVG 甘特）

**Files:**
- Create: `frontend/src/components/vessel-plan/BerthGanttChart.vue`
- Create: `frontend/src/components/vessel-plan/gantt-utils.ts`

- [ ] **Step 1: gantt-utils 纯函数测试（可选 vitest）或手测**

```typescript
export function timeToX(iso: string, startMs: number, endMs: number, width: number): number
export function berthToY(berthIndex: number, rowHeight: number): number
```

- [ ] **Step 2: BerthGanttChart props**

```typescript
defineProps<{
  berths: VpBerth[]
  rows: VpHorizonRow[]
  horizonStart: string
  horizonHours: number
  selectedVoyageId?: string | null
}>()
```

- SVG：Y 轴泊位标签；X 轴时间刻度（0/12/24/36/48h）；每船 rect；等待=ETA 到 ETB 虚线；冲突/warning 红色描边；click emit `select(voyageId)`

- [ ] **Step 3: 与 VesselPlanTab 联动 loadHorizon**

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/vessel-plan/BerthGanttChart.vue frontend/src/components/vessel-plan/gantt-utils.ts
git commit -m "feat(vessel-plan): add berth gantt chart component"
```

---

### Task 11: BerthLayoutMap + VesselPlanList

**Files:**
- Create: `frontend/src/components/vessel-plan/BerthLayoutMap.vue`
- Create: `frontend/src/components/vessel-plan/VesselPlanList.vue`
- Create: `frontend/src/components/vessel-plan/VesselPlanToolbar.vue`
- Create: `frontend/src/components/vessel-plan/VesselPlanSummaryBar.vue`

- [ ] **Step 1: BerthLayoutMap**

SVG rect 按 `position_x/y` 排列；占用 berth 填船名；hover/click emit `berth-select`；显示 yard_zone 色带

- [ ] **Step 2: VesselPlanList**

表格：船名、ETA、ETB、泊位、等待、checkbox；行点击打开抽屉

- [ ] **Step 3: Toolbar**

按钮：重新优化、重算、确认下发(N)、重置演示(admin)

- [ ] **Step 4: SummaryBar**

展示 `agent_summary` + warnings 折叠

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/vessel-plan/
git commit -m "feat(vessel-plan): add layout map, list, toolbar, summary bar"
```

---

### Task 12: VesselTimelineDrawer + 微调

**Files:**
- Create: `frontend/src/components/vessel-plan/VesselTimelineDrawer.vue`
- Create: `frontend/src/components/vessel-plan/VesselPlanAdjustForm.vue`

- [ ] **Step 1: Drawer 竖向时间线**

节点：预计到港 → 靠泊 → 作业 → 离港；展示 agent_note、备选泊位 chips

- [ ] **Step 2: AdjustForm**

泊位 select（标注可行/不可行）；ETB datetime-local；锁定 checkbox；保存 → `patchAssignment`；触发 `recompute`

- [ ] **Step 3: 甘特/平面图选中同步**

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/vessel-plan/VesselTimelineDrawer.vue frontend/src/components/vessel-plan/VesselPlanAdjustForm.vue
git commit -m "feat(vessel-plan): add vessel timeline drawer and adjust form"
```

---

### Task 13: 下发与跳转协同作业

**Files:**
- Modify: `frontend/src/components/vessel-plan/VesselPlanTab.vue`
- Modify: `frontend/src/components/orchestration/OrchestrationTaskView.vue`（可选：emit 打开详情）

- [ ] **Step 1: adopt 流程**

```typescript
async function confirmAdopt() {
  const res = await vesselPlanApi.adopt(selectedIds.value, chatStore.currentSessionId || 'default-session')
  toast.success(t('vesselPlan.adoptSuccess'))
  if (res.task_ids?.[0]) {
    // 切 Tab ops 并 openDetail — 通过 provide/inject 或 router query ?task=
  }
}
```

- [ ] **Step 2: OrchestrationView provide tab switch + openTask**

- [ ] **Step 3: 手测全流程**

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/vessel-plan/VesselPlanTab.vue frontend/src/views/OrchestrationView.vue
git commit -m "feat(vessel-plan): adopt dispatches and navigates to orchestration detail"
```

---

### Task 14: i18n + 文档

**Files:**
- Modify: `frontend/src/i18n/index.ts`
- Modify: `docs/01-项目概览/changelog.md`
- Modify: `docs/01-项目概览/VERSION.md`
- Modify: `docs/04-运维文档/port-operations-user-guide.md`
- Modify: `docs/superpowers/README.md`

- [ ] **Step 1: 补全 zh/en i18n**（`vesselPlan.*`, `orchestration.tab.*`）

- [ ] **Step 2: changelog v4.5.0 条目 + VERSION 下一版本**

- [ ] **Step 3: 用户指南增加「进出港计划」章节**

- [ ] **Step 4: Commit**

```bash
git add frontend/src/i18n/index.ts docs/
git commit -m "docs(v4.5.0): vessel plan feature documentation and i18n"
```

---

### Task 15: 构建与回归验证

- [ ] **Step 1: 后端全量**

Run: `cd backend && python3 -m pytest tests/test_berth_scheduler.py tests/test_vessel_plan_repository.py tests/test_vessel_plan_service.py tests/test_vessel_plan_api.py tests/test_vessel_plan_e2e.py tests/test_port_orchestration_e2e.py -q`
Expected: all PASS

- [ ] **Step 2: 前端构建**

Run: `cd frontend && npx vite build`
Expected: exit 0

- [ ] **Step 3: 浏览器手测清单**

1. `/orchestration` → Tab「进出港计划」
2. 首次自动 seed 或点重置演示
3. 重新优化 → 甘特/平面图有数据
4. 点船 → 抽屉 → 改泊位 → 重算
5. 勾选 → 确认下发 → 切 Tab 协同作业见任务

---

## Spec Coverage Self-Review

| Spec 要求 | Task |
|-----------|------|
| 内置拟真数据 | Task 1–3 |
| 48h + 单船 | Task 2 horizon, Task 12 drawer |
| Agent↔OR 闭环 | Task 4–5 |
| 微调/重算/下发 | Task 5 patch/recompute/adopt, Task 12–13 |
| 泊位甘特+平面图 | Task 10–11 |
| API 全套 | Task 6 |
| orchestration 模块开关 | Task 6 main.py |
| 验收测试 | Task 4, 7, 15 |

## 建议工期

| 阶段 | Task | 约 |
|------|------|-----|
| 后端数据+OR | 1–7 | 3d |
| 前端可视化 | 8–13 | 3d |
| 文档+验收 | 14–15 | 1d |
| **合计** | | **~7 人天** |

---

*Plan version: 2026-05-30*
