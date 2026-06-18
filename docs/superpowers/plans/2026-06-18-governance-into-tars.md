# 数据治理融入 TARS — 阶段0+阶段1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Argus 数据治理（双引擎质量规则）平移成 TARS 新增 module `governance`，接 TARS datasource 脊柱，配 Vue3 治理页。

**Architecture:** 治理作为 optional module 长在 TARS 上。纯函数规则层（builtin 6 类 + GE 封装）从 Argus 原样搬；数据访问层 `fetch_rows` 复用 TARS 已有的 `SQLAgent` 执行 SELECT，输出统一 `ResultSet`；持久化层用 TARS 原生 raw-SQL + `migrations.py` + Repository 模式重写（不照搬 Argus 的 SQLAlchemy ORM）。规则按 `datasource_id`(字符串 UUID) + `table_name` 归属。

**Tech Stack:** Python / FastAPI / 原生 sqlite3+psycopg2 raw SQL / SQLAlchemy（仅 SQLAgent 执行外部库查询用）/ pytest / Vue3 + Vite + Pinia。

**回退基线:** `v5.2.0-pre-fusion`（已 tag + 推 Gitee）。

---

## 关键适配决策（DeepSeek 必读）

源代码在 `/Users/daobanxiang/myproject/Argus/backend/argus/governance/`，但**不能照搬**，因为两套底座不同：

| 维度 | Argus（源） | TARS（目标） | 处理 |
|---|---|---|---|
| 持久化 | SQLAlchemy ORM + AsyncSession | raw SQL + dataclass + Repository + migrations.py | models/service 重写 |
| 数据集标识 | `dataset_id`（int，datasets 表） | `datasource_id`（str UUID，bi_datasources 表）+ `table_name` | 规则改挂 datasource_id+table |
| 取数 | `core.dataset.preview_dataset(conn, ds)` | `SQLAgent(connection_url).execute(sql)` | 新建 `fetch_rows` 适配层 |
| 规则纯函数 | `rules/builtin.py`、GE 封装 | 同样是纯函数 | **原样搬，零改动** |

**可原样搬的（纯函数，零底座依赖）**：`rules/builtin.py`（6 类规则 + RULE_REGISTRY）、`rules/__init__.py`（get_rule_fn）、`expectations/`（GE 封装）。

**必须重写的**：`models.py`（ORM→dataclass）、`service.py`（AsyncSession→Repository）、新增 `fetch_rows`、新增 `repository.py`、新增迁移、新增 router。

**要修的 Argus 遗留 bug**：`engine.py` 返回的 `CheckRun.summary` 里**没有** `rule_results` 键，但 `service.py` 却 `summary.get("rule_results", [])` 去取 → 单行结果永远存不进库。本计划在 engine 改为返回 `rule_results`，service 据此落库。

---

## File Structure

新建 `backend/tars/governance/`：

| 文件 | 职责 |
|---|---|
| `__init__.py` | 包标记 |
| `rules/__init__.py` | get_rule_fn 工厂（Argus 原样搬） |
| `rules/builtin.py` | 6 类纯函数规则 + RULE_REGISTRY（Argus 原样搬） |
| `result_set.py` | `ResultSet` dataclass（rows/column_names/truncated） |
| `expectations/__init__.py` | GE 封装（Argus 原样搬，import 隔离） |
| `expectations/catalog.py` | GE expectation 目录（Argus 原样搬） |
| `models.py` | `QualityRule`/`CheckRun`/`RuleResultRow` dataclass（TARS 风格重写） |
| `engine.py` | 双引擎路由（Argus 搬 + 修 rule_results bug + dataset_id→datasource_id） |
| `datasource_adapter.py` | `fetch_rows()` 复用 SQLAgent 取数 |
| `repository.py` | 三表 raw-SQL CRUD（TARS Repository 模式） |
| `service.py` | run_validation 编排（TARS 风格重写） |
| `api/__init__.py` | 包标记 |
| `api/router.py` | `/api/governance` 路由 |

修改：
- `backend/tars/database/migrations.py`：加治理三表迁移
- `backend/tars/main.py`：条件挂载 governance router + init
- `backend/config/modules.yaml`：注册 governance module

前端新建 `frontend/src/`（具体路径在 Task 10 按实际结构定）：治理页 + api 封装 + store。

---

## 阶段0 — 地基

### Task 1: 治理 module 骨架 + health 路由

**Files:**
- Create: `backend/tars/governance/__init__.py`
- Create: `backend/tars/governance/api/__init__.py`
- Create: `backend/tars/governance/api/router.py`
- Modify: `backend/config/modules.yaml`
- Modify: `backend/tars/main.py`
- Test: `backend/tests/test_governance_health.py`

- [ ] **Step 1: 注册 module 到 modules.yaml**

在 `backend/config/modules.yaml` 的 `modules.optional` 段，`presales` 之后加：

```yaml
    governance:
      enabled: true
      description: "数据治理 — 双引擎质量规则校验"
      requires: [bi]
      routes: ["/api/governance"]
```

- [ ] **Step 2: 写 health 路由（先让测试有目标）**

Create `backend/tars/governance/__init__.py`（空文件即可）。
Create `backend/tars/governance/api/__init__.py`（空文件即可）。
Create `backend/tars/governance/api/router.py`：

```python
"""数据治理 API 路由 — /api/governance"""
from fastapi import APIRouter, Depends
from typing import Optional

from ...database import Database
from ..api._auth import require_module  # 注意：_auth 在 tars/api/，下方 import 修正

router = APIRouter(prefix="/api/governance", tags=["Governance"])

_require = require_module("governance")
router.dependencies = [Depends(_require)]

_db: Optional[Database] = None


def init_governance_api(db: Database) -> None:
    global _db
    _db = db


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "module": "governance"}
```

注意 import 路径：`require_module` 在 `backend/tars/api/_auth.py`。从 `tars/governance/api/router.py` 引用应为：

```python
from ...api._auth import require_module
```

修正后的 router.py 顶部 import 段：

```python
"""数据治理 API 路由 — /api/governance"""
from fastapi import APIRouter, Depends
from typing import Optional

from ...database import Database
from ...api._auth import require_module

router = APIRouter(prefix="/api/governance", tags=["Governance"])

_require = require_module("governance")
router.dependencies = [Depends(_require)]

_db: Optional[Database] = None


def init_governance_api(db: Database) -> None:
    global _db
    _db = db


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "module": "governance"}
```

- [ ] **Step 3: 在 main.py 条件挂载**

在 `backend/tars/main.py` 找到挂载 bi/insight router 的段落（约 `main.py:525-542`，搜索 `is_enabled("bi")`），仿照加入：

```python
    if module_registry.is_enabled("governance"):
        from .governance.api.router import router as governance_router, init_governance_api
        init_governance_api(db)
        app.include_router(governance_router)
```

`db` 变量用该段落里现有的 Database 实例（与 bi 同名，照抄上下文用的那个）。

- [ ] **Step 4: 写 health 测试**

Create `backend/tests/test_governance_health.py`：

```python
"""治理 module health 路由接入测试。"""
import pytest


def test_health_returns_ok(client, auth_headers):
    resp = client.get("/api/governance/health", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["module"] == "governance"
```

先看 `backend/tests/conftest.py` 现有夹具名：用 `setup_main_api_auth(db)` 拿 `(headers, user)`。若没有现成 `client`/`auth_headers` 夹具，则改写为用现有夹具构造，参照同目录其它 `test_*api*.py` 的客户端搭建方式（TestClient(app) + setup_main_api_auth）。

- [ ] **Step 5: 跑测试验证通过**

Run: `cd backend && python -m pytest tests/test_governance_health.py -v`
Expected: PASS（health 返回 ok）。若 401，说明鉴权头没构造对，参照现有 bi/insight 的 api 测试。

- [ ] **Step 6: Commit**

```bash
git add backend/tars/governance/ backend/config/modules.yaml backend/tars/main.py backend/tests/test_governance_health.py
git commit -m "feat(governance): 阶段0 module 骨架 + /api/governance/health"
```

---

### Task 2: ResultSet + 纯函数规则层（Argus 原样搬）

**Files:**
- Create: `backend/tars/governance/result_set.py`
- Create: `backend/tars/governance/rules/__init__.py`
- Create: `backend/tars/governance/rules/builtin.py`
- Test: `backend/tests/test_governance_rules.py`

- [ ] **Step 1: 写 ResultSet dataclass**

Create `backend/tars/governance/result_set.py`：

```python
"""统一行集 — 治理引擎与数据源之间的契约。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResultSet:
    rows: list[list[Any]]
    column_names: list[str]
    truncated: bool = False
```

- [ ] **Step 2: 搬 builtin 规则（从 Argus 原样复制）**

把 `/Users/daobanxiang/myproject/Argus/backend/argus/governance/rules/builtin.py` 整个文件内容复制到 `backend/tars/governance/rules/builtin.py`，**内容一字不改**（它是零依赖纯函数：6 个 validate_* + RuleResult dataclass + RULE_REGISTRY）。

- [ ] **Step 3: 搬规则工厂**

Create `backend/tars/governance/rules/__init__.py`，复制 Argus 的 `rules/__init__.py`，仅改 import 路径前缀：

```python
"""Governance rule registry."""

from tars.governance.rules.builtin import RULE_REGISTRY as _builtin_registry


def get_rule_fn(kind: str):
    fn = _builtin_registry.get(kind)
    if fn is None:
        raise ValueError(f"Unknown rule kind: {kind}. Available: {list(_builtin_registry.keys())}")
    return fn


def available_rules() -> list[str]:
    return list(_builtin_registry.keys())
```

- [ ] **Step 4: 写规则纯函数测试（从 Argus 搬 + 补齐 6 类）**

Create `backend/tests/test_governance_rules.py`：

```python
"""6 类 builtin 规则纯函数测试。"""
from tars.governance.rules.builtin import (
    validate_not_null, validate_unique, validate_range,
    validate_regex, validate_enum, validate_cross_field,
)

COLS = ["id", "name", "age", "start", "end", "status"]
ROWS = [
    [1, "a", 10, 1, 5, "ok"],
    [2, "",  20, 3, 2, "bad"],   # name 空; start>end
    [3, "a", 99, 1, 9, "ok"],    # name 重复; age 超范围
]


def test_not_null():
    r = validate_not_null([row[:2] for row in ROWS], ["id", "name"], {"field": "name"})
    assert r.failed_count == 1 and r.passed_count == 2


def test_unique():
    r = validate_unique([[row[1]] for row in ROWS], ["name"], {"field": "name"})
    assert r.failed_count == 1  # 第三行 "a" 重复


def test_range():
    r = validate_range([[row[2]] for row in ROWS], ["age"], {"field": "age", "min": 0, "max": 60})
    assert r.failed_count == 1  # 99 超范围


def test_regex():
    r = validate_regex([[row[5]] for row in ROWS], ["status"], {"field": "status", "pattern": r"^ok$"})
    assert r.failed_count == 1  # "bad"


def test_enum():
    r = validate_enum([[row[5]] for row in ROWS], ["status"], {"field": "status", "values": ["ok"]})
    assert r.failed_count == 1


def test_cross_field():
    r = validate_cross_field(
        [[row[3], row[4]] for row in ROWS], ["start", "end"],
        {"left": "start", "right": "end", "op": "<="},
    )
    assert r.failed_count == 1  # 第二行 start=3 > end=2


def test_field_not_found_is_graceful():
    r = validate_not_null(ROWS, COLS, {"field": "nonexistent"})
    assert r.sample_violations and "error" in r.sample_violations[0]
```

- [ ] **Step 5: 跑测试验证通过**

Run: `cd backend && python -m pytest tests/test_governance_rules.py -v`
Expected: 7 passed。

- [ ] **Step 6: Commit**

```bash
git add backend/tars/governance/result_set.py backend/tars/governance/rules/ backend/tests/test_governance_rules.py
git commit -m "feat(governance): 搬入 6 类 builtin 规则 + ResultSet 契约"
```

---

### Task 3: fetch_rows 取数适配层（复用 SQLAgent）

**Files:**
- Create: `backend/tars/governance/datasource_adapter.py`
- Test: `backend/tests/test_governance_fetch_rows.py`

- [ ] **Step 1: 写适配层**

Create `backend/tars/governance/datasource_adapter.py`：

```python
"""取数适配层 — 把 datasource_id + 表/SQL 变成内存 ResultSet。

治理与 TARS 数据层之间的唯一接触点。复用 bi 的 SQLAgent 执行只读 SELECT。
"""
from __future__ import annotations

from ..database.bi_store import get_bi_store
from ..bi.sql_agent import SQLAgent
from .result_set import ResultSet


def fetch_rows(
    datasource_id: str,
    *,
    table: str | None = None,
    sql: str | None = None,
    max_rows: int = 10000,
    tenant_id: str = "org_default",
) -> ResultSet:
    """拉取数据源行集供质量校验。

    table 与 sql 二选一、互斥；table 模式生成 SELECT * FROM <table>。
    多拉 1 行用于 truncated 判定。
    """
    if (table is None) == (sql is None):
        raise ValueError("fetch_rows: table 与 sql 必须二选一")

    store = get_bi_store()
    ds = store.get(datasource_id, tenant_id)
    if ds is None:
        raise ValueError(f"数据源不存在: {datasource_id}")

    query = sql if sql is not None else f"SELECT * FROM {table}"

    agent = SQLAgent(ds.connection_url)
    agent.security.max_rows = max_rows + 1  # 多拉一行判断截断
    result = agent.execute(query)

    if not result["success"]:
        raise RuntimeError(f"取数失败: {result['error']}")

    columns = result["columns"]
    data = result["data"]  # List[Dict]
    truncated = len(data) > max_rows
    if truncated:
        data = data[:max_rows]

    # List[Dict] → List[list]，对齐 builtin 规则的入参契约
    rows = [[row.get(c) for c in columns] for row in data]
    return ResultSet(rows=rows, column_names=columns, truncated=truncated)
```

- [ ] **Step 2: 写测试（用临时 SQLite 文件做真实数据源）**

Create `backend/tests/test_governance_fetch_rows.py`：

```python
"""fetch_rows 适配层测试 — 用临时 SQLite 文件做真实外部数据源。"""
import sqlite3
import pytest

from tars.governance.datasource_adapter import fetch_rows
from tars.database.bi_store import init_bi_store


@pytest.fixture
def sqlite_datasource(tmp_path, test_db):
    # 建一个真实 sqlite 文件作外部数据源
    dbfile = tmp_path / "ext.db"
    conn = sqlite3.connect(dbfile)
    conn.execute("CREATE TABLE items (id INTEGER, name TEXT)")
    conn.executemany("INSERT INTO items VALUES (?, ?)", [(i, f"n{i}") for i in range(5)])
    conn.commit()
    conn.close()

    store = init_bi_store(test_db)
    ds = store.create(
        tenant_id="org_default",
        name="ext",
        db_type="sqlite",
        connection_url=f"sqlite:///{dbfile}",
    )
    return ds.id


def test_fetch_table_returns_rows(sqlite_datasource):
    rs = fetch_rows(sqlite_datasource, table="items", tenant_id="org_default")
    assert rs.column_names == ["id", "name"]
    assert len(rs.rows) == 5
    assert rs.truncated is False
    assert rs.rows[0] == [0, "n0"]


def test_truncated_flag(sqlite_datasource):
    rs = fetch_rows(sqlite_datasource, table="items", max_rows=3, tenant_id="org_default")
    assert len(rs.rows) == 3
    assert rs.truncated is True


def test_table_and_sql_mutually_exclusive(sqlite_datasource):
    with pytest.raises(ValueError):
        fetch_rows(sqlite_datasource, table="items", sql="SELECT 1", tenant_id="org_default")


def test_missing_datasource_raises(test_db):
    init_bi_store(test_db)
    with pytest.raises(ValueError):
        fetch_rows("nonexistent-id", table="items", tenant_id="org_default")
```

注意：用到 `test_db` 夹具（conftest 提供的 `:memory:` SQLite）。`bi_datasources` 表需已存在——若 `init_bi_store` 不自动建表，参照 bi 的 api 测试看 datasource 表如何初始化（可能需 `test_db` 触发 schema init）。

- [ ] **Step 3: 跑测试验证通过**

Run: `cd backend && python -m pytest tests/test_governance_fetch_rows.py -v`
Expected: 4 passed。若 `bi_datasources` 表不存在报错，先确认 schema init 已建该表（看 connection.py 的 init_schema 是否含 bi_datasources）。

- [ ] **Step 4: Commit**

```bash
git add backend/tars/governance/datasource_adapter.py backend/tests/test_governance_fetch_rows.py
git commit -m "feat(governance): fetch_rows 取数适配层(复用 SQLAgent)"
```

---

## 阶段1 — 治理后端平移

### Task 4: 三表迁移 + models dataclass

**Files:**
- Modify: `backend/tars/database/migrations.py`
- Create: `backend/tars/governance/models.py`
- Test: `backend/tests/test_governance_migration.py`

- [ ] **Step 1: 加迁移函数**

在 `backend/tars/database/migrations.py` 末尾、`MIGRATIONS` 列表定义之前，加迁移函数（仿照 `_m2_agent_decisions` 的方言无关写法，TEXT/INTEGER/TIMESTAMP，JSON 以 TEXT 存）：

```python
def _m_governance_tables(cursor) -> None:
    """治理三表:quality_rules / check_runs / rule_results。

    规则按 datasource_id(str UUID)+table_name 归属,带 user_id 对齐单组织多用户。
    """
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS quality_rules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            datasource_id TEXT NOT NULL,
            table_name TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL,
            params TEXT NOT NULL DEFAULT '{}',
            engine TEXT NOT NULL DEFAULT 'builtin',
            enabled INTEGER NOT NULL DEFAULT 1,
            user_id TEXT NOT NULL DEFAULT 'default',
            created_at TIMESTAMP
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_qrules_ds ON quality_rules(datasource_id, table_name)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS check_runs (
            id TEXT PRIMARY KEY,
            datasource_id TEXT NOT NULL,
            table_name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            total_rows INTEGER NOT NULL DEFAULT 0,
            truncated INTEGER NOT NULL DEFAULT 0,
            summary TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            user_id TEXT NOT NULL DEFAULT 'default',
            created_at TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rule_results (
            id TEXT PRIMARY KEY,
            check_run_id TEXT NOT NULL,
            rule_id TEXT NOT NULL,
            rule_name TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL DEFAULT '',
            engine TEXT NOT NULL DEFAULT 'builtin',
            passed_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            sample_violations TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_rresults_run ON rule_results(check_run_id)"
    )
```

把它加进 `MIGRATIONS` 列表，version 取当前最大值+1（**实施时读文件确认现有最大 version，不要写死**）：

```python
    (N + 1, "governance quality tables", _m_governance_tables),
```

- [ ] **Step 2: 写 models dataclass**

Create `backend/tars/governance/models.py`：

```python
"""治理数据模型 — TARS 风格 dataclass(非 SQLAlchemy ORM)。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityRule:
    id: str
    datasource_id: str
    kind: str
    name: str = ""
    table_name: str = ""
    params: dict = field(default_factory=dict)
    engine: str = "builtin"  # "builtin" | "great_expectations"
    enabled: bool = True
    user_id: str = "default"
    created_at: str | None = None


@dataclass
class CheckRun:
    id: str
    datasource_id: str
    table_name: str = ""
    status: str = "pending"  # pending/passed/failed/error
    total_rows: int = 0
    truncated: bool = False
    summary: dict = field(default_factory=dict)
    error: str | None = None
    user_id: str = "default"
    created_at: str | None = None


@dataclass
class RuleResultRow:
    id: str
    check_run_id: str
    rule_id: str
    rule_name: str = ""
    kind: str = ""
    engine: str = "builtin"
    passed_count: int = 0
    failed_count: int = 0
    sample_violations: list[Any] = field(default_factory=list)
```

- [ ] **Step 3: 写迁移测试**

Create `backend/tests/test_governance_migration.py`：

```python
"""治理三表迁移建表测试。"""

def test_governance_tables_exist(test_db):
    conn = test_db._get_conn()
    cur = conn.cursor()
    for tbl in ("quality_rules", "check_runs", "rule_results"):
        cur.execute(f"SELECT * FROM {tbl} LIMIT 0")  # 不报错即表存在
```

注意：`test_db` 夹具初始化时应已跑过 `apply_migrations`。若没有，确认 conftest 的 test_db 是否触发完整 schema init；参照其它依赖迁移表的测试（如 agent_decisions）怎么拿到建好表的 db。

- [ ] **Step 4: 跑测试验证通过**

Run: `cd backend && python -m pytest tests/test_governance_migration.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/tars/database/migrations.py backend/tars/governance/models.py backend/tests/test_governance_migration.py
git commit -m "feat(governance): 三表迁移 + models dataclass"
```

---

### Task 5: repository raw-SQL CRUD

**Files:**
- Create: `backend/tars/governance/repository.py`
- Test: `backend/tests/test_governance_repository.py`

- [ ] **Step 1: 写 repository**

Create `backend/tars/governance/repository.py`：

```python
"""治理持久化 — raw-SQL CRUD(TARS Repository 模式)。"""
from __future__ import annotations

import json
import uuid

from ..database.base import Database, get_local_now
from .models import QualityRule, CheckRun, RuleResultRow


class GovernanceRepository:
    def __init__(self, db: Database):
        self.db = db

    def _now(self) -> str:
        return get_local_now().isoformat()

    # ── quality_rules ──
    def create_rule(self, *, datasource_id: str, kind: str, name: str = "",
                    table_name: str = "", params: dict | None = None,
                    engine: str = "builtin", user_id: str = "default") -> QualityRule:
        rid = str(uuid.uuid4())
        now = self._now()
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO quality_rules
               (id, name, datasource_id, table_name, kind, params, engine, enabled, user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (rid, name, datasource_id, table_name, kind,
             json.dumps(params or {}, ensure_ascii=False), engine, user_id, now),
        )
        conn.commit()
        return QualityRule(id=rid, datasource_id=datasource_id, kind=kind, name=name,
                           table_name=table_name, params=params or {}, engine=engine,
                           enabled=True, user_id=user_id, created_at=now)

    def list_rules(self, *, datasource_id: str, table_name: str | None = None,
                   user_id: str = "default", enabled_only: bool = False) -> list[QualityRule]:
        conn = self.db._get_conn()
        cur = conn.cursor()
        q = ("SELECT id, name, datasource_id, table_name, kind, params, engine, enabled, user_id, created_at "
             "FROM quality_rules WHERE datasource_id = ? AND user_id = ?")
        args: list = [datasource_id, user_id]
        if table_name is not None:
            q += " AND table_name = ?"
            args.append(table_name)
        if enabled_only:
            q += " AND enabled = 1"
        q += " ORDER BY created_at DESC"
        cur.execute(q, args)
        return [self._row_to_rule(r) for r in cur.fetchall()]

    def _row_to_rule(self, r) -> QualityRule:
        return QualityRule(
            id=r[0], name=r[1], datasource_id=r[2], table_name=r[3], kind=r[4],
            params=json.loads(r[5] or "{}"), engine=r[6], enabled=bool(r[7]),
            user_id=r[8], created_at=r[9],
        )

    def delete_rule(self, rule_id: str, user_id: str = "default") -> None:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM quality_rules WHERE id = ? AND user_id = ?", (rule_id, user_id))
        conn.commit()

    # ── check_runs + rule_results ──
    def save_check_run(self, run: CheckRun, results: list[RuleResultRow]) -> CheckRun:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO check_runs
               (id, datasource_id, table_name, status, total_rows, truncated, summary, error, user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run.id, run.datasource_id, run.table_name, run.status, run.total_rows,
             1 if run.truncated else 0, json.dumps(run.summary, ensure_ascii=False),
             run.error, run.user_id, run.created_at or self._now()),
        )
        for rr in results:
            cur.execute(
                """INSERT INTO rule_results
                   (id, check_run_id, rule_id, rule_name, kind, engine, passed_count, failed_count, sample_violations)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (rr.id, rr.check_run_id, rr.rule_id, rr.rule_name, rr.kind, rr.engine,
                 rr.passed_count, rr.failed_count, json.dumps(rr.sample_violations, ensure_ascii=False)),
            )
        conn.commit()
        return run

    def get_check_run(self, run_id: str, user_id: str = "default") -> CheckRun | None:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            ("SELECT id, datasource_id, table_name, status, total_rows, truncated, summary, error, user_id, created_at "
             "FROM check_runs WHERE id = ? AND user_id = ?"),
            (run_id, user_id),
        )
        r = cur.fetchone()
        if not r:
            return None
        return CheckRun(
            id=r[0], datasource_id=r[1], table_name=r[2], status=r[3], total_rows=r[4],
            truncated=bool(r[5]), summary=json.loads(r[6] or "{}"), error=r[7],
            user_id=r[8], created_at=r[9],
        )
```

- [ ] **Step 2: 写 repository 测试**

Create `backend/tests/test_governance_repository.py`：

```python
"""治理 repository CRUD 测试。"""
import uuid

from tars.governance.repository import GovernanceRepository
from tars.governance.models import CheckRun, RuleResultRow


def test_create_and_list_rule(test_db):
    repo = GovernanceRepository(test_db)
    rule = repo.create_rule(datasource_id="ds1", kind="not_null",
                            name="名称非空", table_name="items",
                            params={"field": "name"}, user_id="u1")
    assert rule.id
    rules = repo.list_rules(datasource_id="ds1", user_id="u1")
    assert len(rules) == 1 and rules[0].kind == "not_null"
    assert rules[0].params == {"field": "name"}


def test_user_isolation(test_db):
    repo = GovernanceRepository(test_db)
    repo.create_rule(datasource_id="ds1", kind="unique", params={"field": "id"}, user_id="u1")
    assert repo.list_rules(datasource_id="ds1", user_id="u2") == []


def test_save_and_get_check_run(test_db):
    repo = GovernanceRepository(test_db)
    run = CheckRun(id=str(uuid.uuid4()), datasource_id="ds1", table_name="items",
                   status="passed", total_rows=10, user_id="u1")
    rr = RuleResultRow(id=str(uuid.uuid4()), check_run_id=run.id, rule_id="r1",
                       rule_name="x", kind="not_null", passed_count=10)
    repo.save_check_run(run, [rr])
    got = repo.get_check_run(run.id, user_id="u1")
    assert got is not None and got.status == "passed" and got.total_rows == 10
```

- [ ] **Step 3: 跑测试验证通过**

Run: `cd backend && python -m pytest tests/test_governance_repository.py -v`
Expected: 3 passed。

- [ ] **Step 4: Commit**

```bash
git add backend/tars/governance/repository.py backend/tests/test_governance_repository.py
git commit -m "feat(governance): repository raw-SQL CRUD"
```

---

### Task 6: engine 双引擎路由（搬 + 修 bug + datasource 化）

**Files:**
- Create: `backend/tars/governance/engine.py`
- Create: `backend/tars/governance/expectations/__init__.py`
- Create: `backend/tars/governance/expectations/catalog.py`
- Test: `backend/tests/test_governance_engine.py`

- [ ] **Step 1: 搬 GE 封装（import 隔离，原样搬）**

把 Argus 的 `expectations/__init__.py` 与 `expectations/catalog.py` 复制到 `backend/tars/governance/expectations/`，仅改文件内 import 前缀 `argus.` → `tars.`。这两个文件把 `great_expectations` 的 import 隔离在内部，缺失时优雅降级——保持原样。

- [ ] **Step 2: 写 engine（基于 Argus engine，做三处改造）**

Create `backend/tars/governance/engine.py`。相对 Argus 原版**三处改造**：①入参 `rules` 用 TARS dataclass `QualityRule`；②`CheckRun.summary` 里**新增 `rule_results` 键**（修 Argus 落库 bug）；③`CheckRun` 改用 TARS dataclass，按 `datasource_id`+`table_name` 而非 `dataset_id`。

```python
"""治理校验引擎 — builtin + GE 双引擎,在 ResultSet 上跑规则。"""
from __future__ import annotations

import uuid

from .rules import get_rule_fn
from .rules.builtin import RuleResult as BuiltinRuleResult
from .result_set import ResultSet
from .models import QualityRule, CheckRun, RuleResultRow


def run_checks(
    result_set: ResultSet,
    rules: list[QualityRule],
    *,
    datasource_id: str,
    table_name: str = "",
    user_id: str = "default",
    ge_engine=None,
) -> tuple[CheckRun, list[RuleResultRow]]:
    """在 ResultSet 上执行规则,返回 (CheckRun 汇总, 单规则结果行列表)。"""
    total_passed = 0
    total_failed = 0
    result_rows: list[RuleResultRow] = []
    errors: list[str] = []
    run_id = str(uuid.uuid4())

    builtin_rules = [r for r in rules if r.engine == "builtin" and r.enabled]
    ge_rules = [r for r in rules if r.engine == "great_expectations" and r.enabled]

    # ── builtin ──
    for rule in builtin_rules:
        try:
            fn = get_rule_fn(rule.kind)
            res: BuiltinRuleResult = fn(result_set.rows, result_set.column_names, rule.params)
            result_rows.append(RuleResultRow(
                id=str(uuid.uuid4()), check_run_id=run_id, rule_id=rule.id,
                rule_name=rule.name, kind=rule.kind, engine="builtin",
                passed_count=res.passed_count, failed_count=res.failed_count,
                sample_violations=res.sample_violations,
            ))
            total_passed += res.passed_count
            total_failed += res.failed_count
        except Exception as e:
            result_rows.append(RuleResultRow(
                id=str(uuid.uuid4()), check_run_id=run_id, rule_id=rule.id,
                rule_name=rule.name, kind=rule.kind, engine="builtin",
            ))
            errors.append(f"Rule '{rule.name}' failed: {e}")

    # ── GE ──
    if ge_rules and ge_engine is not None:
        try:
            import pandas as pd
            df = pd.DataFrame(result_set.rows, columns=result_set.column_names)
            suite = ge_engine.create_suite("tars_check", [
                {"type": r.kind, "kwargs": r.params} for r in ge_rules
            ])
            ge_result = ge_engine.validate(suite, df)
            for i, r in enumerate(ge_rules):
                ge_rr = ge_result["results"][i] if i < len(ge_result["results"]) else {}
                ok = ge_rr.get("success", False)
                result_rows.append(RuleResultRow(
                    id=str(uuid.uuid4()), check_run_id=run_id, rule_id=r.id,
                    rule_name=r.name, kind=r.kind, engine="great_expectations",
                    passed_count=ge_rr.get("result", {}).get("element_count", 0) if ok else 0,
                    failed_count=0 if ok else 1,
                    sample_violations=ge_rr.get("result", {}).get("unexpected_list", [])[:20],
                ))
                total_passed += result_rows[-1].passed_count
                total_failed += result_rows[-1].failed_count
        except Exception as e:
            errors.append(f"GE engine failed: {e}")
    elif ge_rules and ge_engine is None:
        for r in ge_rules:
            result_rows.append(RuleResultRow(
                id=str(uuid.uuid4()), check_run_id=run_id, rule_id=r.id,
                rule_name=r.name, kind=r.kind, engine="great_expectations",
            ))
            errors.append(f"Rule '{r.name}': GE engine not available")

    status = "error" if errors else ("passed" if total_failed == 0 else "failed")
    summary = {
        "total_passed": total_passed,
        "total_failed": total_failed,
        "rules_checked": len(rules),
        "rules_passed": len([rr for rr in result_rows if rr.failed_count == 0]),
        "rules_failed": len([rr for rr in result_rows if rr.failed_count > 0]),
        "errors": errors,
        "rule_results": [  # ← 修 Argus bug:summary 内带单规则结果,供前端直接渲染
            {"rule_id": rr.rule_id, "rule_name": rr.rule_name, "kind": rr.kind,
             "engine": rr.engine, "passed_count": rr.passed_count,
             "failed_count": rr.failed_count, "sample_violations": rr.sample_violations}
            for rr in result_rows
        ],
    }
    run = CheckRun(
        id=run_id, datasource_id=datasource_id, table_name=table_name,
        total_rows=len(result_set.rows), truncated=result_set.truncated,
        summary=summary, status=status,
        error="; ".join(errors) if errors else None, user_id=user_id,
    )
    return run, result_rows
```

- [ ] **Step 3: 写 engine 测试**

Create `backend/tests/test_governance_engine.py`：

```python
"""engine 双引擎路由 + summary.rule_results 测试。"""
from tars.governance.engine import run_checks
from tars.governance.result_set import ResultSet
from tars.governance.models import QualityRule


def _rs():
    return ResultSet(rows=[[1, "a"], [2, None]], column_names=["id", "name"], truncated=False)


def test_builtin_failure_counted():
    rules = [QualityRule(id="r1", datasource_id="ds1", kind="not_null",
                         name="名称非空", params={"field": "name"})]
    run, rows = run_checks(_rs(), rules, datasource_id="ds1", table_name="t")
    assert run.status == "failed"
    assert len(rows) == 1 and rows[0].failed_count == 1


def test_summary_contains_rule_results():
    rules = [QualityRule(id="r1", datasource_id="ds1", kind="not_null", params={"field": "name"})]
    run, _ = run_checks(_rs(), rules, datasource_id="ds1")
    assert "rule_results" in run.summary
    assert run.summary["rule_results"][0]["failed_count"] == 1


def test_ge_missing_degrades_not_crash():
    rules = [QualityRule(id="r2", datasource_id="ds1", kind="expect_column_values_to_not_be_null",
                         engine="great_expectations", params={"column": "name"})]
    run, rows = run_checks(_rs(), rules, datasource_id="ds1", ge_engine=None)
    assert run.status == "error"
    assert any("not available" in e for e in run.summary["errors"])


def test_all_pass():
    rules = [QualityRule(id="r1", datasource_id="ds1", kind="not_null", params={"field": "id"})]
    run, _ = run_checks(_rs(), rules, datasource_id="ds1")
    assert run.status == "passed"
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd backend && python -m pytest tests/test_governance_engine.py -v`
Expected: 4 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/tars/governance/engine.py backend/tars/governance/expectations/ backend/tests/test_governance_engine.py
git commit -m "feat(governance): 双引擎 engine(修 rule_results 落库 bug + datasource 化)"
```

---

### Task 7: service 编排 + API 路由

**Files:**
- Create: `backend/tars/governance/service.py`
- Modify: `backend/tars/governance/api/router.py`
- Test: `backend/tests/test_governance_api.py`

- [ ] **Step 1: 写 service**

Create `backend/tars/governance/service.py`：

```python
"""治理编排 — 取数 → 跑规则 → 落库,返回 QualityReport。"""
from __future__ import annotations

from ..database.base import Database
from .repository import GovernanceRepository
from .datasource_adapter import fetch_rows
from .engine import run_checks
from .models import CheckRun


class GovernanceService:
    def __init__(self, db: Database):
        self.repo = GovernanceRepository(db)

    def run_validation(self, *, datasource_id: str, table_name: str,
                       user_id: str = "default", tenant_id: str = "org_default",
                       ge_engine=None) -> CheckRun:
        rules = self.repo.list_rules(datasource_id=datasource_id, table_name=table_name,
                                     user_id=user_id, enabled_only=True)
        if not rules:
            run = CheckRun(id=__import__("uuid").uuid4().hex, datasource_id=datasource_id,
                           table_name=table_name, status="passed", total_rows=0,
                           summary={"message": "未配置规则", "rule_results": []}, user_id=user_id)
            self.repo.save_check_run(run, [])
            return run

        rs = fetch_rows(datasource_id, table=table_name, tenant_id=tenant_id)
        run, result_rows = run_checks(rs, rules, datasource_id=datasource_id,
                                      table_name=table_name, user_id=user_id, ge_engine=ge_engine)
        self.repo.save_check_run(run, result_rows)
        return run
```

- [ ] **Step 2: 扩展 router（加规则 CRUD + 跑校验）**

把 `backend/tars/governance/api/router.py` 在 health 之后扩展（保留 Task 1 写好的顶部 import + init）。追加：

```python
from pydantic import BaseModel
from fastapi import HTTPException
from ..repository import GovernanceRepository
from ..service import GovernanceService
from ..rules import available_rules
from ...api._auth import Principal, require_authenticated_user


class RuleCreate(BaseModel):
    datasource_id: str
    table_name: str
    kind: str
    name: str = ""
    params: dict = {}
    engine: str = "builtin"


@router.get("/rule-kinds")
def rule_kinds() -> dict:
    return {"kinds": available_rules()}


@router.get("/rules")
def list_rules(datasource_id: str, table_name: str | None = None,
               principal: Principal = Depends(require_authenticated_user)) -> dict:
    repo = GovernanceRepository(_db)
    rules = repo.list_rules(datasource_id=datasource_id, table_name=table_name,
                            user_id=principal.user_id)
    return {"rules": [r.__dict__ for r in rules]}


@router.post("/rules")
def create_rule(body: RuleCreate,
                principal: Principal = Depends(require_authenticated_user)) -> dict:
    repo = GovernanceRepository(_db)
    rule = repo.create_rule(datasource_id=body.datasource_id, kind=body.kind,
                            name=body.name, table_name=body.table_name,
                            params=body.params, engine=body.engine,
                            user_id=principal.user_id)
    return rule.__dict__


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str,
                principal: Principal = Depends(require_authenticated_user)) -> dict:
    GovernanceRepository(_db).delete_rule(rule_id, user_id=principal.user_id)
    return {"deleted": rule_id}


@router.post("/validate")
def validate(datasource_id: str, table_name: str,
             principal: Principal = Depends(require_authenticated_user)) -> dict:
    try:
        run = GovernanceService(_db).run_validation(
            datasource_id=datasource_id, table_name=table_name,
            user_id=principal.user_id, tenant_id=principal.tenant_id)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return run.__dict__
```

注意 import：service/repository 在 `tars/governance/`，从 `tars/governance/api/router.py` 引用用 `..`（如 `from ..service import GovernanceService`）。`require_authenticated_user`/`Principal` 在 `tars/api/_auth.py`，用 `...api._auth`。

- [ ] **Step 3: 写 API 集成测试**

Create `backend/tests/test_governance_api.py`：

```python
"""治理 API 端到端:建数据源 → 建规则 → 跑校验 → QualityReport。"""
import sqlite3
import pytest
from fastapi.testclient import TestClient

from tars.main import app
from tars.database.bi_store import init_bi_store


@pytest.fixture
def ctx(tmp_path, test_db):
    # 真实外部 sqlite 数据源
    dbfile = tmp_path / "ext.db"
    c = sqlite3.connect(dbfile)
    c.execute("CREATE TABLE items (id INTEGER, name TEXT)")
    c.executemany("INSERT INTO items VALUES (?, ?)", [(1, "a"), (2, None), (3, "c")])
    c.commit(); c.close()
    store = init_bi_store(test_db)
    ds = store.create(tenant_id="org_default", name="ext", db_type="sqlite",
                      connection_url=f"sqlite:///{dbfile}")
    # 认证头(参照 conftest)
    from tests.conftest import setup_main_api_auth  # 若不可直接 import,用 fixture 形式
    headers, _user = setup_main_api_auth(test_db)
    return TestClient(app), headers, ds.id


def test_full_flow(ctx):
    client, headers, ds_id = ctx
    # 建规则:name 非空
    r = client.post("/api/governance/rules", headers=headers, json={
        "datasource_id": ds_id, "table_name": "items", "kind": "not_null",
        "name": "名称非空", "params": {"field": "name"}})
    assert r.status_code == 200
    # 跑校验
    r2 = client.post(f"/api/governance/validate?datasource_id={ds_id}&table_name=items",
                     headers=headers)
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "failed"  # 有 1 个 null
    assert body["summary"]["rule_results"][0]["failed_count"] == 1
```

注意：认证头构造以 conftest 实际暴露的夹具为准（`setup_main_api_auth` 可能是 fixture 而非可直接 import 的函数）。实施时先读 conftest，按其约定拿 headers。若 module 未启用导致 403，确认 modules.yaml 里 governance.enabled=true 且 test 环境加载了该配置。

- [ ] **Step 4: 跑测试验证通过**

Run: `cd backend && python -m pytest tests/test_governance_api.py -v`
Expected: PASS（全链路 failed + rule_results 有 1 个 failed）。

- [ ] **Step 5: 跑全量治理测试确保无回归**

Run: `cd backend && python -m pytest tests/ -k governance -v`
Expected: 所有 governance 测试 PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/tars/governance/service.py backend/tars/governance/api/router.py backend/tests/test_governance_api.py
git commit -m "feat(governance): service 编排 + 规则CRUD/校验 API"
```

---

### Task 8: 后端端到端验收 + 全量回归

**Files:**
- 无新增；仅运行验收

- [ ] **Step 1: 跑全量后端测试确保无回归**

Run: `cd backend && python -m pytest tests/ -q`
Expected: 原有 169 测试 + 新增治理测试全部 PASS。若有失败，先看是否治理改动碰坏了既有模块（治理是新增 module，不应影响其它，若有失败优先排查 main.py 挂载段落是否误改）。

- [ ] **Step 2: 手工端到端冒烟（真实启动）**

Run: `cd backend && python -m tars.main`（或项目实际启动命令，看 README/main.py 底部）。
启动后用 curl 验证全链路（替换 <token> 为有效 JWT 或 X-API-Key）：

```bash
# 1. health
curl -s localhost:8000/api/governance/health -H "X-API-Key: <key>"
# 期望 {"status":"ok","module":"governance"}

# 2. 规则类型
curl -s localhost:8000/api/governance/rule-kinds -H "X-API-Key: <key>"
# 期望 6 类:not_null/unique/range/regex/enum/cross_field
```

数据源建一个连本地 SQLite 的（通过 /api/datasources 既有接口），再建规则、跑 /validate，确认拿到含 rule_results 的报告。

- [ ] **Step 3: 验证 GE 缺失降级（若环境未装 great_expectations）**

建一个 engine="great_expectations" 的规则跑校验，确认返回 status=error + "GE engine not available"，而非进程崩溃。

- [ ] **Step 4: Commit（若 Step 1-3 暴露并修了 bug）**

```bash
git add -A && git commit -m "test(governance): 后端端到端验收 + 回归修复"
```

若全绿无需修，跳过本 commit。

---

## 阶段1 — Vue3 治理页

> 前端约定（已核实）：页面在 `frontend/src/views/*.vue`，API 统一走 `frontend/src/api/index.ts`（axios），路由在 `frontend/src/router/index.ts`（懒加载 + meta.requiresAuth），可参照 `BiAnalyticsView.vue` + `components/bi/DataSourceSettings.vue` + `composables/useBiDataSources.ts`。不引入新 UI 框架，复用现有组件库。

### Task 9: 前端 API 封装 + 路由注册

**Files:**
- Create: `frontend/src/api/governance.ts`
- Modify: `frontend/src/router/index.ts`
- Test: `frontend/src/api/governance.spec.ts`

- [ ] **Step 1: 写 governance API 封装**

Create `frontend/src/api/governance.ts`（沿用 `api/index.ts` 的 axios 实例；若该文件导出共享 axios 实例则 import 复用，否则参照其 baseURL/拦截器写法）：

```typescript
import axios from 'axios'

const http = axios.create({ baseURL: '/api/governance' })

export interface QualityRule {
  id: string
  datasource_id: string
  table_name: string
  kind: string
  name: string
  params: Record<string, unknown>
  engine: string
  enabled: boolean
}

export interface RuleResult {
  rule_id: string
  rule_name: string
  kind: string
  engine: string
  passed_count: number
  failed_count: number
  sample_violations: unknown[]
}

export interface CheckRunReport {
  id: string
  datasource_id: string
  table_name: string
  status: string
  total_rows: number
  truncated: boolean
  summary: { rule_results: RuleResult[]; total_passed: number; total_failed: number; errors: string[] }
}

export const governanceApi = {
  ruleKinds: () => http.get<{ kinds: string[] }>('/rule-kinds').then(r => r.data.kinds),
  listRules: (datasourceId: string, table?: string) =>
    http.get<{ rules: QualityRule[] }>('/rules', { params: { datasource_id: datasourceId, table_name: table } }).then(r => r.data.rules),
  createRule: (body: Partial<QualityRule>) => http.post<QualityRule>('/rules', body).then(r => r.data),
  deleteRule: (id: string) => http.delete(`/rules/${id}`).then(r => r.data),
  validate: (datasourceId: string, table: string) =>
    http.post<CheckRunReport>('/validate', null, { params: { datasource_id: datasourceId, table_name: table } }).then(r => r.data),
}
```

注意：鉴权头注入以 `api/index.ts` 现有做法为准（多半有 axios 拦截器统一加 Authorization/X-API-Key）。**实施时先读 `api/index.ts`，若其导出可复用的 http 实例，直接 import 用它而非新建 axios.create**，确保鉴权头一致。

- [ ] **Step 2: 注册路由**

在 `frontend/src/router/index.ts` 的 routes 数组里，仿照 memory/settings 加：

```typescript
    {
      path: '/governance',
      name: 'governance',
      component: () => import('@/views/GovernanceView.vue'),
      meta: { requiresAuth: true }
    },
```

（GovernanceView.vue 在 Task 10 创建；本步先注册路由，构建时会因组件不存在报错——可先建一个空壳 `<template><div/></template>` 占位，Task 10 再填充。）

- [ ] **Step 3: 写 API 封装测试**

Create `frontend/src/api/governance.spec.ts`（参照同目录现有 .spec.ts 的 mock 写法，多半用 vitest + vi.mock('axios')）：

```typescript
import { describe, it, expect, vi } from 'vitest'
import { governanceApi } from './governance'

describe('governanceApi', () => {
  it('listRules 传 datasource_id 参数', async () => {
    // 参照现有 spec 的 axios mock 方式断言请求 URL/params
    expect(typeof governanceApi.listRules).toBe('function')
    expect(typeof governanceApi.validate).toBe('function')
  })
})
```

实施时按现有 spec 风格补全 mock 断言（mock http.get 返回 {data:{rules:[]}}，断言参数）。

- [ ] **Step 4: 跑测试**

Run: `cd frontend && npx vitest run src/api/governance.spec.ts`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/governance.ts frontend/src/router/index.ts frontend/src/api/governance.spec.ts
git commit -m "feat(governance-fe): API 封装 + 路由注册"
```

---

### Task 10: GovernanceView 治理页

**Files:**
- Create/Modify: `frontend/src/views/GovernanceView.vue`（Task 9 占位 → 填充）
- Test: `frontend/src/views/GovernanceView.spec.ts`

- [ ] **Step 1: 写治理页组件**

填充 `frontend/src/views/GovernanceView.vue`。功能：选数据源 + 表 → 规则列表 → 新建规则（按 kind 动态参数）→ 跑校验 → 报告。复用现有 UI 组件库（参照 BiAnalyticsView.vue 用的组件，如表格/表单/按钮——**实施时先看 BiAnalyticsView.vue 用的是哪套组件，照用**）。

骨架（组件名按项目实际库替换，下例用语义占位）：

```vue
<template>
  <div class="governance-view">
    <header>
      <h2>数据治理 — 质量规则</h2>
      <!-- 数据源 + 表选择,复用 useBiDataSources 拿数据源列表 -->
      <select v-model="datasourceId">
        <option v-for="ds in datasources" :key="ds.id" :value="ds.id">{{ ds.name }}</option>
      </select>
      <input v-model="tableName" placeholder="表名" />
    </header>

    <!-- 规则列表 -->
    <section v-if="datasourceId">
      <button @click="loadRules">刷新规则</button>
      <button @click="showCreate = true">新建规则</button>
      <table>
        <tr v-for="r in rules" :key="r.id">
          <td>{{ r.name || r.kind }}</td>
          <td>{{ r.kind }}</td>
          <td>{{ r.engine }}</td>
          <td><button @click="removeRule(r.id)">删除</button></td>
        </tr>
      </table>
      <button :disabled="!tableName" @click="runValidate">跑校验</button>
    </section>

    <!-- 新建规则表单:按 kind 动态参数 -->
    <div v-if="showCreate" class="rule-form">
      <select v-model="form.kind">
        <option v-for="k in ruleKinds" :key="k" :value="k">{{ k }}</option>
      </select>
      <input v-model="form.name" placeholder="规则名" />
      <!-- not_null/unique/range/regex/enum 用 field;cross_field 用 left/right/op -->
      <input v-if="form.kind !== 'cross_field'" v-model="form.field" placeholder="字段名" />
      <template v-if="form.kind === 'range'">
        <input v-model.number="form.min" placeholder="min" />
        <input v-model.number="form.max" placeholder="max" />
      </template>
      <input v-if="form.kind === 'regex'" v-model="form.pattern" placeholder="正则" />
      <input v-if="form.kind === 'enum'" v-model="form.values" placeholder="允许值,逗号分隔" />
      <template v-if="form.kind === 'cross_field'">
        <input v-model="form.left" placeholder="左字段" />
        <input v-model="form.right" placeholder="右字段" />
        <input v-model="form.op" placeholder="op 如 <=" />
      </template>
      <button @click="submitRule">保存</button>
      <button @click="showCreate = false">取消</button>
    </div>

    <!-- 校验报告 -->
    <section v-if="report" class="report">
      <p>状态：{{ report.status }} | 行数：{{ report.total_rows }}
        <span v-if="report.truncated">（基于前 {{ report.total_rows }} 行抽样）</span>
      </p>
      <p>通过 {{ report.summary.total_passed }} / 失败 {{ report.summary.total_failed }}</p>
      <table>
        <tr v-for="rr in report.summary.rule_results" :key="rr.rule_id">
          <td>{{ rr.rule_name || rr.kind }}</td>
          <td>通过 {{ rr.passed_count }}</td>
          <td>失败 {{ rr.failed_count }}</td>
          <td>{{ JSON.stringify(rr.sample_violations.slice(0, 3)) }}</td>
        </tr>
      </table>
      <p v-if="report.summary.errors.length" class="errors">{{ report.summary.errors.join('; ') }}</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { governanceApi, type QualityRule, type CheckRunReport } from '@/api/governance'
import { useBiDataSources } from '@/composables/useBiDataSources'

const { datasources, loadDataSources } = useBiDataSources()  // 按 composable 实际导出名调整
const datasourceId = ref('')
const tableName = ref('')
const rules = ref<QualityRule[]>([])
const ruleKinds = ref<string[]>([])
const report = ref<CheckRunReport | null>(null)
const showCreate = ref(false)
const form = reactive<any>({ kind: 'not_null', name: '', field: '', min: null, max: null, pattern: '', values: '', left: '', right: '', op: '<=' })

onMounted(async () => {
  await loadDataSources()
  ruleKinds.value = await governanceApi.ruleKinds()
})

async function loadRules() {
  rules.value = await governanceApi.listRules(datasourceId.value, tableName.value || undefined)
}

function buildParams(): Record<string, unknown> {
  const k = form.kind
  if (k === 'cross_field') return { left: form.left, right: form.right, op: form.op }
  if (k === 'range') return { field: form.field, min: form.min, max: form.max }
  if (k === 'regex') return { field: form.field, pattern: form.pattern }
  if (k === 'enum') return { field: form.field, values: form.values.split(',').map((s: string) => s.trim()) }
  return { field: form.field }
}

async function submitRule() {
  await governanceApi.createRule({
    datasource_id: datasourceId.value, table_name: tableName.value,
    kind: form.kind, name: form.name, params: buildParams(), engine: 'builtin',
  })
  showCreate.value = false
  await loadRules()
}

async function removeRule(id: string) {
  await governanceApi.deleteRule(id)
  await loadRules()
}

async function runValidate() {
  report.value = await governanceApi.validate(datasourceId.value, tableName.value)
}
</script>
```

注意：`useBiDataSources` 的实际导出名/返回字段以该 composable 真实代码为准（实施前先读 `frontend/src/composables/useBiDataSources.ts`）。UI 组件、样式类名以项目现有约定为准，别引入新框架。

- [ ] **Step 2: 写组件测试**

Create `frontend/src/views/GovernanceView.spec.ts`（参照 `BiAnalyticsView.spec.ts` 的挂载 + mock 方式）：

```typescript
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/api/governance', () => ({
  governanceApi: {
    ruleKinds: vi.fn().mockResolvedValue(['not_null', 'unique', 'range', 'regex', 'enum', 'cross_field']),
    listRules: vi.fn().mockResolvedValue([]),
    createRule: vi.fn(), deleteRule: vi.fn(),
    validate: vi.fn().mockResolvedValue({ status: 'passed', total_rows: 0, truncated: false,
      summary: { rule_results: [], total_passed: 0, total_failed: 0, errors: [] } }),
  },
}))
vi.mock('@/composables/useBiDataSources', () => ({
  useBiDataSources: () => ({ datasources: { value: [] }, loadDataSources: vi.fn() }),
}))

import GovernanceView from './GovernanceView.vue'

describe('GovernanceView', () => {
  it('挂载后加载规则类型', async () => {
    const wrapper = mount(GovernanceView)
    await new Promise(r => setTimeout(r, 0))
    expect(wrapper.text()).toContain('数据治理')
  })
})
```

实施时按 BiAnalyticsView.spec.ts 的真实 mock 风格调整（store/router stub 等）。

- [ ] **Step 3: 跑测试**

Run: `cd frontend && npx vitest run src/views/GovernanceView.spec.ts`
Expected: PASS。

- [ ] **Step 4: 构建验证**

Run: `cd frontend && npx vue-tsc --noEmit && npx vite build`
Expected: 类型检查 + 构建通过，无 GovernanceView 相关报错。

- [ ] **Step 5: 全量前端测试无回归**

Run: `cd frontend && npx vitest run`
Expected: 原有测试 + 新增治理测试全 PASS。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/GovernanceView.vue frontend/src/views/GovernanceView.spec.ts
git commit -m "feat(governance-fe): 治理页(规则CRUD + 跑校验 + 报告)"
```

---

## 验收总览

阶段0+阶段1 完成的硬指标（对应 spec 第三节）：

1. `config/modules.yaml` 开 governance，`/api/governance/health` 返回 ok。
2. 建一个连 SQLite 的 datasource（走既有 /api/datasources），在治理页配非空规则，跑校验，拿到含通过率 + 异常样本 + truncated 标注的 QualityReport。
3. 同一个 `datasource_id` 既能被 BI/insight 用，又能被治理校验——防割裂硬指标达成。
4. GE 未安装时优雅降级，builtin 规则照常工作。
5. 后端 169 既有测试 + 新增治理测试全绿；前端既有测试 + 治理测试全绿。

**砍掉的（YAGNI，留后续阶段）**：报表、鉴数联动、文件类连接器、字段加密、标准库、血缘、AI 推断规则。
