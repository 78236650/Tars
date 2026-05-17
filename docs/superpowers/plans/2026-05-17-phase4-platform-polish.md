# Phase 4: Platform Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add modular startup (enable/disable feature modules via config) and skill usage tracking (Curator lite). Final integration testing and documentation.

**Architecture:** New `config/modules.yaml` controls which optional modules load. `SkillCurator` records usage stats in SQLite. Both are lightweight additions that don't change existing behavior.

**Tech Stack:** Python 3.8+, FastAPI, SQLite, YAML config

**Dependencies:** Phase 1-3 complete (security, performance, providers all in place)

---

## File Structure

```
config/
└── modules.yaml                 # Module enable/disable config

backend/tars/
├── modules/
│   ├── __init__.py              # Module loader
│   └── registry.py             # Module registry + status API
└── skills/
    └── curator.py               # Skill usage tracking

backend/tests/
├── test_module_loader.py
└── test_skill_curator.py
```

---

## Task 1: Module Config — modules.yaml

**Files:**
- Create: `config/modules.yaml`

- [ ] **Step 1: Create modules config**

```yaml
# config/modules.yaml
modules:
  core:
    - agent
    - tools
    - skills
    - memory
    - auth
    - security

  optional:
    meeting:
      enabled: false
      description: "会议助手（录音转写 + 摘要）"
      routes: ["/api/meeting"]
    bi:
      enabled: false
      description: "BI 工作台（数据分析 + 可视化）"
      routes: ["/api/bi"]
    knowledge:
      enabled: true
      description: "知识库（文档解析 + RAG）"
      routes: ["/api/knowledge"]
    skillhub:
      enabled: true
      description: "SkillHub 技能市场"
      routes: ["/api/skillhub"]
```

- [ ] **Step 2: Commit**

```bash
git add config/modules.yaml
git commit -m "feat(modules): add modules.yaml for optional module configuration"
```

---

## Task 2: Module Loader — 条件路由注册

**Files:**
- Create: `backend/tars/modules/__init__.py`
- Create: `backend/tars/modules/registry.py`
- Create: `backend/tests/test_module_loader.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_module_loader.py
import pytest
from tars.modules.registry import ModuleRegistry

class TestModuleRegistry:
    def setup_method(self):
        self.registry = ModuleRegistry()

    def test_load_config(self):
        self.registry.load()
        assert "meeting" in self.registry.optional_modules
        assert "knowledge" in self.registry.optional_modules

    def test_meeting_disabled_by_default(self):
        self.registry.load()
        assert self.registry.is_enabled("meeting") is False

    def test_knowledge_enabled_by_default(self):
        self.registry.load()
        assert self.registry.is_enabled("knowledge") is True

    def test_list_modules(self):
        self.registry.load()
        modules = self.registry.list_modules()
        assert any(m["name"] == "meeting" for m in modules)
        for m in modules:
            assert "name" in m
            assert "enabled" in m
            assert "description" in m

    def test_core_modules_always_enabled(self):
        self.registry.load()
        assert self.registry.is_core("agent") is True
        assert self.registry.is_core("meeting") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_module_loader.py -v`
Expected: FAIL (import error)

- [ ] **Step 3: Implement module registry**

```python
# backend/tars/modules/__init__.py
from .registry import ModuleRegistry, module_registry

__all__ = ["ModuleRegistry", "module_registry"]
```

```python
# backend/tars/modules/registry.py
import yaml
from pathlib import Path
from typing import Dict, List

class ModuleRegistry:
    def __init__(self):
        self.core_modules: List[str] = []
        self.optional_modules: Dict[str, dict] = {}

    def load(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "modules.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            self.core_modules = ["agent", "tools", "skills", "memory", "auth", "security"]
            return

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        modules = config.get("modules", {})
        self.core_modules = modules.get("core", [])
        self.optional_modules = modules.get("optional", {})

    def is_enabled(self, module_name: str) -> bool:
        if module_name in self.core_modules:
            return True
        mod = self.optional_modules.get(module_name, {})
        return mod.get("enabled", False)

    def is_core(self, module_name: str) -> bool:
        return module_name in self.core_modules

    def list_modules(self) -> List[Dict]:
        result = []
        for name in self.core_modules:
            result.append({"name": name, "enabled": True, "core": True, "description": ""})
        for name, cfg in self.optional_modules.items():
            result.append({
                "name": name,
                "enabled": cfg.get("enabled", False),
                "core": False,
                "description": cfg.get("description", ""),
            })
        return result

    def get_routes(self, module_name: str) -> List[str]:
        mod = self.optional_modules.get(module_name, {})
        return mod.get("routes", [])

# Global singleton
module_registry = ModuleRegistry()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_module_loader.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/tars/modules/__init__.py backend/tars/modules/registry.py backend/tests/test_module_loader.py
git commit -m "feat(modules): implement ModuleRegistry with YAML config loading"
```

---

## Task 3: Conditional Route Registration in main.py

**Files:**
- Modify: `backend/tars/main.py`

- [ ] **Step 1: Add conditional router registration**

In `backend/tars/main.py`, wrap optional module router imports and registrations:

```python
from tars.modules import module_registry
module_registry.load()

# Always register core routers
app.include_router(tools_router)
app.include_router(skills_router)
app.include_router(sessions_router)
app.include_router(memory_router)
app.include_router(audit_router)
app.include_router(admin_router)

# Conditionally register optional routers
if module_registry.is_enabled("bi"):
    from tars.api.bi import router as bi_router, init_bi_api
    app.include_router(bi_router)
    # init_bi_api(...)

if module_registry.is_enabled("knowledge"):
    from tars.api.knowledge import router as knowledge_router, init_knowledge_api
    app.include_router(knowledge_router)

if module_registry.is_enabled("meeting"):
    from tars.api.meeting import router as meeting_router, init_meeting_api
    app.include_router(meeting_router)

if module_registry.is_enabled("skillhub"):
    from tars.api.skillhub import router as skillhub_router, init_skillhub_api
    app.include_router(skillhub_router)

# Module status API
@app.get("/api/modules")
async def get_modules():
    return module_registry.list_modules()
```

- [ ] **Step 2: Verify disabled modules return 404**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -c "
from tars.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
# meeting is disabled
r = client.get('/api/meeting/settings')
print(f'meeting: {r.status_code}')  # Should be 404
# modules endpoint works
r = client.get('/api/modules')
print(f'modules: {r.status_code}')  # Should be 200
"`
Expected: meeting: 404, modules: 200

- [ ] **Step 3: Commit**

```bash
git add backend/tars/main.py
git commit -m "feat(modules): conditional route registration based on modules.yaml"
```

---

## Task 4: Skill Curator — 使用统计

**Files:**
- Create: `backend/tars/skills/curator.py`
- Create: `backend/tests/test_skill_curator.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_skill_curator.py
import pytest
from unittest.mock import MagicMock
from tars.skills.curator import SkillCurator

class TestSkillCurator:
    def setup_method(self):
        self.db = MagicMock()
        self.db._get_conn.return_value = MagicMock()
        self.curator = SkillCurator(self.db)

    def test_record_usage(self):
        self.curator.record_usage(
            skill_id="weather",
            tenant_id="user1",
            trigger_source="router",
            success=True,
            duration_ms=50,
        )
        conn = self.db._get_conn()
        conn.cursor().execute.assert_called()

    def test_get_stats_returns_dict(self):
        self.db._get_conn().cursor().fetchall.return_value = [
            ("weather", 10, 9, "2026-05-17T10:00:00", 45),
        ]
        stats = self.curator.get_stats()
        assert len(stats) == 1
        assert stats[0]["skill_id"] == "weather"
        assert stats[0]["total_calls"] == 10
        assert stats[0]["success_count"] == 9

    def test_get_skill_stats(self):
        self.db._get_conn().cursor().fetchone.return_value = (10, 9, "2026-05-17T10:00:00", 45)
        stat = self.curator.get_skill_stats("weather")
        assert stat["total_calls"] == 10

    def test_archive_skill(self):
        self.curator.archive("weather")
        assert "weather" in self.curator._archived

    def test_activate_skill(self):
        self.curator.archive("weather")
        self.curator.activate("weather")
        assert "weather" not in self.curator._archived

    def test_is_archived(self):
        assert self.curator.is_archived("weather") is False
        self.curator.archive("weather")
        assert self.curator.is_archived("weather") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_skill_curator.py -v`
Expected: FAIL (import error)

- [ ] **Step 3: Implement SkillCurator**

```python
# backend/tars/skills/curator.py
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set

def _now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()

class SkillCurator:
    def __init__(self, db):
        self.db = db
        self._archived: Set[str] = set()
        self._init_table()

    def _init_table(self):
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skill_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                invoked_at TEXT NOT NULL,
                trigger_source TEXT,
                success INTEGER DEFAULT 1,
                duration_ms INTEGER
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_skill_usage_skill ON skill_usage(skill_id, invoked_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_skill_usage_tenant ON skill_usage(tenant_id, invoked_at)")
        conn.commit()

    def record_usage(self, skill_id: str, tenant_id: str, trigger_source: str = "router",
                     success: bool = True, duration_ms: int = 0):
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO skill_usage (skill_id, tenant_id, invoked_at, trigger_source, success, duration_ms) VALUES (?,?,?,?,?,?)",
            (skill_id, tenant_id, _now_iso(), trigger_source, 1 if success else 0, duration_ms),
        )
        conn.commit()

    def get_stats(self) -> List[Dict]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT skill_id, COUNT(*) as total, SUM(success) as successes,
                   MAX(invoked_at) as last_used, AVG(duration_ms) as avg_ms
            FROM skill_usage GROUP BY skill_id ORDER BY total DESC
        """).fetchall()
        return [
            {"skill_id": r[0], "total_calls": r[1], "success_count": r[2],
             "last_used": r[3], "avg_duration_ms": round(r[4] or 0)}
            for r in rows
        ]

    def get_skill_stats(self, skill_id: str) -> Optional[Dict]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        row = cursor.execute("""
            SELECT COUNT(*), SUM(success), MAX(invoked_at), AVG(duration_ms)
            FROM skill_usage WHERE skill_id = ?
        """, (skill_id,)).fetchone()
        if not row or row[0] == 0:
            return None
        return {"total_calls": row[0], "success_count": row[1],
                "last_used": row[2], "avg_duration_ms": round(row[3] or 0)}

    def archive(self, skill_id: str):
        self._archived.add(skill_id)

    def activate(self, skill_id: str):
        self._archived.discard(skill_id)

    def is_archived(self, skill_id: str) -> bool:
        return skill_id in self._archived

# Global singleton
skill_curator: Optional[SkillCurator] = None

def init_skill_curator(db) -> SkillCurator:
    global skill_curator
    skill_curator = SkillCurator(db)
    return skill_curator
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_skill_curator.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/tars/skills/curator.py backend/tests/test_skill_curator.py
git commit -m "feat(skills): implement SkillCurator with usage tracking and archive"
```

---

## Task 5: Integrate Curator into SkillRouter + API

**Files:**
- Modify: `backend/tars/skills/router.py`
- Modify: `backend/tars/api/skills.py`
- Modify: `backend/tars/main.py`

- [ ] **Step 1: Skip archived skills in SkillRouter**

In `backend/tars/skills/router.py`, add check in `route()`:

```python
from .curator import skill_curator

# In route() method, after checking _forced_off:
if skill_curator and skill_curator.is_archived(skill.id):
    continue
```

- [ ] **Step 2: Add stats and archive endpoints to skills API**

In `backend/tars/api/skills.py`:

```python
from tars.skills.curator import skill_curator

@router.get("/stats")
async def get_skill_stats():
    if not skill_curator:
        return []
    return skill_curator.get_stats()

@router.get("/{skill_id}/stats")
async def get_single_skill_stats(skill_id: str):
    if not skill_curator:
        return {"error": "curator not initialized"}
    return skill_curator.get_skill_stats(skill_id) or {"total_calls": 0}

@router.put("/{skill_id}/archive")
async def archive_skill(skill_id: str):
    if skill_curator:
        skill_curator.archive(skill_id)
    return {"status": "ok", "skill_id": skill_id, "state": "archived"}

@router.put("/{skill_id}/activate")
async def activate_skill(skill_id: str):
    if skill_curator:
        skill_curator.activate(skill_id)
    return {"status": "ok", "skill_id": skill_id, "state": "active"}
```

- [ ] **Step 3: Initialize curator in main.py**

```python
from tars.skills.curator import init_skill_curator
_skill_curator = init_skill_curator(db)
```

- [ ] **Step 4: Run tests for regression**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/tars/skills/router.py backend/tars/api/skills.py backend/tars/main.py
git commit -m "feat(skills): integrate curator into router and expose stats API"
```

---

## Task 6: Full Regression + Documentation Prep

- [ ] **Step 1: Run complete test suite**

```bash
cd /Users/daobanxiang/myproject/TARS/backend
python -m pytest tests/ -v --tb=short
```
Expected: ALL PASS (existing + new tests from Phase 1-4)

- [ ] **Step 2: Verify startup with all phases integrated**

```bash
cd /Users/daobanxiang/myproject/TARS/backend
time python -c "from tars.main import app; print('startup ok')"
```
Expected: < 3 seconds, no errors

- [ ] **Step 3: Verify module API**

```bash
cd /Users/daobanxiang/myproject/TARS/backend
python -c "
from tars.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
print(client.get('/api/modules').json())
print(client.get('/api/providers').json())
print(client.get('/api/skills/stats').json())
"
```
Expected: All return valid JSON

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test: verify full Phase 1-4 integration"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | modules.yaml config | — |
| 2 | ModuleRegistry | 5 |
| 3 | Conditional route registration | — |
| 4 | SkillCurator | 6 |
| 5 | Curator integration + API | — |
| 6 | Full regression | — |
| **Total** | | **11+** |
