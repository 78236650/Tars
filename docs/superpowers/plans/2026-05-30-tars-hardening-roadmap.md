# TARS 工程加固与产品化路线图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 TARS v4.3.2 从"单人快速产出的功能完整原型"加固为"可信、可扩展、可对外集成"的工程资产,分三阶段交付。

**Architecture:** P0 用 Gitee Go CI + pre-commit 建立可信交付闭环;同时把三个上帝文件(`database/base.py` 2972 行、`agent.py` 1262 行、`main.py` 1406 行)按职责拆分。P1 在 `database/base.py` 拆出的 repository 层之上引入抽象接口,为未来 Postgres 留缝(本轮不迁移)。P2 把 memory / evolution 子系统抽成对外 MCP server 并加 dashboard。

**Tech Stack:** Python 3.11 + FastAPI、原生 sqlite3(经 repository 层封装)、Vue3 + Vite、pytest、ruff/mypy/black/isort、Gitee Go(`.workflow/` YAML)、pre-commit。

**决策锚点(用户已确认):**
1. CI 平台 = Gitee Go(`.workflow/` YAML,驱动现有 Makefile 目标)
2. DB = 只解耦到 repository 层,**不迁移** Postgres(留接口)
3. 重构 = 三个上帝文件**全部拆分**
4. 范围 = P0→P1→P2 全要,分阶段

---

## File Structure(决策锁定)

**P0-CI(新建):**
- `.workflow/ci.yml` — Gitee Go 流水线:lint + test + 前端 build
- `.pre-commit-config.yaml` — 本地预检(ruff/black/isort + pytest -q 快测)
- `backend/pyproject.toml` — 补 `[tool.ruff]`/`[tool.mypy]`/`[tool.pytest.ini_options]` 配置(若缺)

**P0-Refactor(`database/base.py` 拆分):** 现 `Database` 单类 91 方法,按 8 个领域拆为 repository:
- `backend/tars/database/connection.py` — 连接管理 + `_init_db` 建表(从 base.py 迁出)
- `backend/tars/database/models.py` — 全部 `@dataclass`(Session/Message/Memory/CronJob/...)
- `backend/tars/database/repositories/session_repo.py` — session + message + working_context
- `backend/tars/database/repositories/memory_repo.py` — memory(~30 方法,最大块)
- `backend/tars/database/repositories/cron_repo.py` — cronjob + reminder_notification
- `backend/tars/database/repositories/transcription_repo.py` — transcription + document_file
- `backend/tars/database/base.py` — 保留 `Database` 类作为**门面(facade)**,委派给各 repo,**对外签名不变**(零调用方改动)

**P0-Refactor(`agent.py` / `main.py` 拆分):**
- `backend/tars/agent/loop.py` — agent 主循环(从 agent.py 迁出)
- `backend/tars/agent/prompt_builder.py` — system prompt 拼装
- `backend/tars/agent/tool_runner.py` — 工具调用执行
- `backend/tars/agent/agent.py` — 保留 `AgentV2` 类协调上述模块
- `backend/tars/app_factory.py` — `create_app()` + 路由注册(从 main.py 迁出)
- `backend/tars/lifespan.py` — startup/shutdown 钩子
- `backend/tars/main.py` — 仅 `app = create_app()` 入口

**P1-DB 抽象:**
- `backend/tars/database/repositories/base_repo.py` — `Protocol` 接口定义,标注 Postgres 迁移点
- `backend/tars/database/sql_dialect.py` — SQL 方言隔离(FTS5 vs tsvector 等差异收口)

**P2-Productization:**
- `mcp/tars_memory_server.py` — 独立 MCP server 暴露 memory(search/add)
- `backend/tars/api/evolution_metrics.py` — evolution dashboard 数据 API
- `frontend/src/views/EvolutionDashboard.vue` — 采纳率/反馈可视化
- (evolution MCP server 不做,见末尾"显式排除")

---
# PHASE P0 — 可信可交付(变现前提)

## Task 1: 补全 lint/test/format 工具配置

**Files:**
- Modify: `backend/pyproject.toml`(补 ruff/mypy/pytest 段,若已存在则对齐)

- [ ] **Step 1: 确认当前配置缺口**

Run: `grep -E "\[tool\.(ruff|mypy|pytest)" backend/pyproject.toml`
Expected: 若无输出,说明三段都缺,需补全。

- [ ] **Step 2: 追加工具配置到 pyproject.toml**

在 `backend/pyproject.toml` 末尾追加(已存在的段跳过):

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
exclude = ["venv", "__pycache__", "data"]

[tool.ruff.lint]
select = ["E", "F", "I", "W"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true
exclude = ["venv", "data"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 3: 本地验证配置可用**

Run: `cd backend && ruff check . --quiet; pytest -q --co | tail -3`
Expected: ruff 能跑(可能报已有告警,正常);pytest 能收集到测试用例。

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore(ci): add ruff/mypy/pytest tool configuration"
```

---

## Task 2: 建立 Gitee Go 流水线

**Files:**
- Create: `.workflow/ci.yml`

- [ ] **Step 1: 创建流水线 YAML**

> 注:Gitee Go 用 `.workflow/` 目录下的 YAML;不同账号的扩展(extension)ID 可能有版本差异。本文件用 `shell-exec` 驱动现有 Makefile,可移植性最强。落地后在 Gitee Go 控制台确认 `python`/`nodejs` 环境扩展版本号。

写入 `.workflow/ci.yml`:

```yaml
name: TARS CI
displayName: TARS CI
triggers:
  push:
    - branches:
        precise:
          - main
          - v4.3.2
  pr:
    - branches:
        precise:
          - main
stages:
  - name: lint-and-test
    displayName: Lint & Test
    failFast: true
    jobs:
      backend:
        name: backend
        runsOn: ubuntu-latest
        steps:
          - name: setup-python
            uses: shell-exec
            with:
              shell: |
                python3 -m venv backend/venv
                . backend/venv/bin/activate
                pip install -r backend/requirements.txt
          - name: lint
            uses: shell-exec
            with:
              shell: |
                . backend/venv/bin/activate
                cd backend && ruff check .
          - name: test
            uses: shell-exec
            with:
              shell: |
                . backend/venv/bin/activate
                cd backend && pytest -q
      frontend:
        name: frontend
        runsOn: ubuntu-latest
        steps:
          - name: build
            uses: shell-exec
            with:
              shell: |
                cd frontend && npm ci && npm run build
```

- [ ] **Step 2: 本地预演 CI 会跑的命令(不依赖 Gitee)**

Run: `cd backend && ruff check . ; echo "---" ; pytest -q 2>&1 | tail -5`
Expected: 看到 lint 结果与测试通过/失败汇总。**若有失败,先记录,Task 3+ 不引入新失败即可。**

- [ ] **Step 3: Commit**

```bash
git add .workflow/ci.yml
git commit -m "ci: add Gitee Go pipeline running lint, tests, and frontend build"
```

---

## Task 3: 配置 pre-commit 本地预检

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: 创建 pre-commit 配置**

写入 `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff
        name: ruff
        entry: bash -c 'cd backend && ruff check --fix .'
        language: system
        types: [python]
        pass_filenames: false
      - id: black
        name: black
        entry: bash -c 'cd backend && black .'
        language: system
        types: [python]
        pass_filenames: false
      - id: pytest-quick
        name: pytest-quick
        entry: bash -c 'cd backend && pytest -q -x'
        language: system
        pass_filenames: false
        stages: [pre-push]
```

- [ ] **Step 2: 安装并验证**

Run: `pip install pre-commit && pre-commit install && pre-commit install --hook-type pre-push`
Expected: `pre-commit installed at .git/hooks/pre-commit`

- [ ] **Step 3: 干跑一次**

Run: `pre-commit run --all-files 2>&1 | tail -10`
Expected: ruff/black 跑过(可能自动修复部分文件)。

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: add pre-commit hooks for ruff, black, and pre-push tests"
```

---
## Task 4: 为 Database 类写表征测试(拆分前的安全网)

**Files:**
- Test: `backend/tests/test_database_facade_characterization.py`

拆 2972 行的 `Database` 类前,先用测试锁住对外行为。拆分后这些测试必须**全部仍通过**——这是"签名不变"的客观证据。

- [ ] **Step 1: 写表征测试覆盖每个领域的代表方法**

写入 `backend/tests/test_database_facade_characterization.py`:

```python
import tempfile, os
import pytest
from tars.database.base import Database


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    d = Database(db_path=path)
    yield d
    d.close()
    os.unlink(path)


def test_session_message_roundtrip(db):
    s = db.create_session(agent_id="a", user_id="u", tenant_id="t", title="hi")
    db.add_message(s.id, "user", "hello")
    msgs = db.get_messages(s.id)
    assert [m.content for m in msgs] == ["hello"]
    assert db.get_session(s.id, tenant_id="t").title == "hi"


def test_memory_crud_and_search(db):
    m = db.add_memory(content="user likes Go", category="user_preference", tenant_id="t")
    assert db.get_memory(m.id, tenant_id="t").content == "user likes Go"
    hits = db.search_memories("Go", limit=5, tenant_id="t")
    assert any("Go" in h.content for h in hits)


def test_cronjob_lifecycle(db):
    c = db.create_cronjob(user_id="u", name="job", schedule="* * * * *", prompt="x")
    assert db.get_cronjob(c.id) is not None
    db.delete_cronjob(c.id)
    assert db.get_cronjob(c.id) is None


def test_working_context_upsert(db):
    db.upsert_working_context("sess1", tenant_id="t", goal="ship")
    assert db.get_working_context("sess1", tenant_id="t").get("goal") == "ship"
```

- [ ] **Step 2: 运行——必须全过(锁定现状)**

Run: `cd backend && pytest tests/test_database_facade_characterization.py -v`
Expected: 4 passed。**若某方法签名与测试不符,以真实签名为准修正测试**(读 `database/base.py` 对应行),目的是锁住真实行为。

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_database_facade_characterization.py
git commit -m "test(db): add characterization tests for Database facade before refactor"
```

---

## Task 5: 拆出 models + connection

**Files:**
- Create: `backend/tars/database/models.py`
- Create: `backend/tars/database/connection.py`
- Modify: `backend/tars/database/base.py`(移出 dataclass 与连接/建表逻辑,改为 import)

- [ ] **Step 1: 迁移 dataclass 到 models.py**

把 `base.py` 中的 `get_local_now`、`_parse_db_datetime` 及全部 `@dataclass`(`Session` `Message` `Memory` `CronJob` `ReminderNotification` `Transcription` `AuditLog` `ApprovalRequest`)整段剪切到新文件 `backend/tars/database/models.py`,文件顶部保留原 import(`datetime`/`dataclass`/`typing`)。

- [ ] **Step 2: 迁移连接与建表到 connection.py**

把 `Database.__init__`/`_get_conn`/`close`/`_init_db`(base.py 第 153–897 行的连接与建表部分)迁到 `backend/tars/database/connection.py` 的 `class ConnectionManager`,暴露 `get_conn()` / `close()` / `init_schema()`。

- [ ] **Step 3: base.py 改为引用**

在 `base.py` 顶部加:

```python
from tars.database.models import (
    get_local_now, Session, Message, Memory, CronJob,
    ReminderNotification, Transcription, AuditLog, ApprovalRequest,
)
from tars.database.connection import ConnectionManager
```

`Database.__init__` 改为持有 `self._cm = ConnectionManager(db_path)`,`_get_conn` 委派 `return self._cm.get_conn()`。

- [ ] **Step 4: 跑表征测试,必须仍全过**

Run: `cd backend && pytest tests/test_database_facade_characterization.py -v`
Expected: 4 passed(行为不变)。

- [ ] **Step 5: Commit**

```bash
git add backend/tars/database/models.py backend/tars/database/connection.py backend/tars/database/base.py
git commit -m "refactor(db): extract dataclasses to models.py and connection mgmt to connection.py"
```

---

## Task 6: 拆出各领域 repository,base.py 变门面

**Files:**
- Create: `backend/tars/database/repositories/__init__.py`
- Create: `backend/tars/database/repositories/session_repo.py`
- Create: `backend/tars/database/repositories/memory_repo.py`
- Create: `backend/tars/database/repositories/cron_repo.py`
- Create: `backend/tars/database/repositories/transcription_repo.py`
- Modify: `backend/tars/database/base.py`(瘦身为门面)

每个 repo 接收 `ConnectionManager`,持有领域方法。`Database` 门面保留**所有原 public 方法名与签名**,内部委派给对应 repo。这样 24+ API 路由与各模块**零改动**。

- [ ] **Step 1: 创建 repositories 包并迁移 session 域**

`repositories/session_repo.py` 定义 `class SessionRepo:`,`__init__(self, cm)` 持有连接管理器,迁入 base.py 的:`create_session` `get_session` `get_session_metadata` `set_session_metadata` `add_message` `get_messages` `list_sessions` `delete_session` `update_session_title` `get_working_context` `upsert_working_context` `cleanup_working_contexts`。方法体内 `self._get_conn()` 改为 `self._cm.get_conn()`。

- [ ] **Step 2: 迁移 memory / cron / transcription 域**

同样模式:
- `memory_repo.py` `class MemoryRepo:` — 迁入所有 `*_memory*`/`*_memories*`/`decay_importance`/`cleanup_old_memories`/`forget_core_line`/`*_kb_promotion*`/`_memory_from_row`/`_update_memory_access` 方法(~30 个)。
- `cron_repo.py` `class CronRepo:` — 迁入 `*_cronjob*` + `*_reminder_notification*` + `_row_to_cronjob` + `_row_to_reminder_notification`。
- `transcription_repo.py` `class TranscriptionRepo:` — 迁入 `*_transcription*` + `*_document_file*`。

- [ ] **Step 3: base.py 改为门面委派**

`Database.__init__` 内实例化各 repo:

```python
def __init__(self, db_path: Optional[str] = None):
    self._cm = ConnectionManager(db_path)
    self._cm.init_schema()
    self.sessions = SessionRepo(self._cm)
    self.memories = MemoryRepo(self._cm)
    self.crons = CronRepo(self._cm)
    self.transcriptions = TranscriptionRepo(self._cm)
```

对每个原 public 方法,保留一行委派(签名完全不变),例如:

```python
def create_session(self, *args, **kwargs):
    return self.sessions.create_session(*args, **kwargs)

def search_memories(self, *args, **kwargs):
    return self.memories.search_memories(*args, **kwargs)
```

- [ ] **Step 4: 跑表征测试 + 全量测试**

Run: `cd backend && pytest tests/test_database_facade_characterization.py -v && pytest -q 2>&1 | tail -5`
Expected: 表征测试 4 passed;全量测试相对 Task 2 基线**不新增失败**。

- [ ] **Step 5: 确认 base.py 显著瘦身**

Run: `wc -l backend/tars/database/base.py`
Expected: 从 2972 行降到约 200–400 行(纯门面委派)。

- [ ] **Step 6: Commit**

```bash
git add backend/tars/database/repositories backend/tars/database/base.py
git commit -m "refactor(db): split Database god-class into domain repositories with facade delegation"
```

---
## Task 7: 拆分 agent.py(1262 行)

**Files:**
- Create: `backend/tars/agent/prompt_builder.py`
- Create: `backend/tars/agent/tool_runner.py`
- Create: `backend/tars/agent/loop.py`
- Modify: `backend/tars/agent/agent.py`(瘦身为协调者)
- Test: `backend/tests/test_agent_smoke.py`(若已有 agent 测试则复用)

- [ ] **Step 1: 先确认现有 agent 测试覆盖,补一个 smoke 表征测试**

Run: `ls backend/tests/ | grep -i agent`
若无,写入 `backend/tests/test_agent_smoke.py` 一个最小实例化测试:

```python
from tars.agent.agent import AgentV2

def test_agent_instantiates():
    a = AgentV2(tenant_id="default", user_id="u")
    assert a is not None
```

Run: `cd backend && pytest tests/test_agent_smoke.py -v`
Expected: 1 passed(若 `AgentV2` 构造签名不同,读 `agent.py` 修正参数后再跑通)。

- [ ] **Step 2: 抽出 prompt 拼装到 prompt_builder.py**

把 `agent.py` 中负责拼 system prompt(加载 SOUL/AGENTS/MEMORY/USER + 拼接)的方法迁到 `prompt_builder.py` 的 `def build_system_prompt(workspace, memory, user_profile) -> str`,`AgentV2` 改为调用它。

- [ ] **Step 3: 抽出工具执行到 tool_runner.py**

把工具调用循环中"解析 tool_call → dispatch → 收集结果"的逻辑迁到 `tool_runner.py` 的 `async def run_tool_calls(tool_calls, dispatcher) -> list`。

- [ ] **Step 4: 抽出主循环到 loop.py**

把 LLM 流式调用 + 工具循环的核心迁到 `loop.py` 的 `async def run_agent_loop(agent, messages) -> ...`,`AgentV2` 仅保留状态与对外方法,委派给 loop。

- [ ] **Step 5: 跑 smoke + 全量,确认不回归**

Run: `cd backend && pytest tests/test_agent_smoke.py -v && pytest -q 2>&1 | tail -5`
Expected: smoke passed;全量不新增失败。

- [ ] **Step 6: Commit**

```bash
git add backend/tars/agent/ backend/tests/test_agent_smoke.py
git commit -m "refactor(agent): split AgentV2 into prompt_builder, tool_runner, and loop modules"
```

---

## Task 8: 拆分 main.py(1406 行)

**Files:**
- Create: `backend/tars/app_factory.py`
- Create: `backend/tars/lifespan.py`
- Modify: `backend/tars/main.py`(瘦身为入口)
- Test: `backend/tests/test_app_boots.py`

- [ ] **Step 1: 写应用启动表征测试**

写入 `backend/tests/test_app_boots.py`:

```python
from fastapi.testclient import TestClient
from tars.main import app

def test_app_has_routes():
    client = TestClient(app)
    paths = {r.path for r in app.routes}
    assert any(p.startswith("/api") for p in paths)
```

Run: `cd backend && pytest tests/test_app_boots.py -v`
Expected: 1 passed(确认当前可启动)。

- [ ] **Step 2: 抽出 create_app 到 app_factory.py**

把 main.py 里 `FastAPI(...)` 实例化、中间件、`include_router` 注册整段迁到 `app_factory.py` 的 `def create_app() -> FastAPI:`。

- [ ] **Step 3: 抽出 startup/shutdown 到 lifespan.py**

把启动钩子(DB 初始化、cron 调度器启动、模块加载等)迁到 `lifespan.py` 的 `@asynccontextmanager async def lifespan(app):`,在 `create_app()` 中传入 `FastAPI(lifespan=lifespan)`。

- [ ] **Step 4: main.py 瘦身**

`main.py` 仅保留:

```python
from tars.app_factory import create_app
app = create_app()
```

- [ ] **Step 5: 跑启动测试 + 全量**

Run: `cd backend && pytest tests/test_app_boots.py -v && pytest -q 2>&1 | tail -5`
Expected: passed;全量不新增失败。

- [ ] **Step 6: Commit**

```bash
git add backend/tars/app_factory.py backend/tars/lifespan.py backend/tars/main.py backend/tests/test_app_boots.py
git commit -m "refactor(app): extract create_app to app_factory and startup to lifespan"
```

---

# PHASE P1 — 突破扩展性天花板(DB 抽象,不迁移)

## Task 9: 定义 repository 接口 + SQL 方言隔离

**Files:**
- Create: `backend/tars/database/repositories/base_repo.py`
- Create: `backend/tars/database/sql_dialect.py`
- Modify: 各 repo(让其继承/标注接口)

目标:把"哪些地方是 SQLite 专有"显式化,为未来切 Postgres 划清边界——**本轮不写任何 Postgres 实现**。

- [ ] **Step 1: 写方言隔离测试**

写入 `backend/tests/test_sql_dialect.py`:

```python
from tars.database.sql_dialect import fulltext_match_clause

def test_sqlite_fts_clause():
    clause = fulltext_match_clause("sqlite", "col", "kw")
    assert "MATCH" in clause or "LIKE" in clause
```

Run: `cd backend && pytest tests/test_sql_dialect.py -v`
Expected: FAIL(模块不存在)。

- [ ] **Step 2: 实现 sql_dialect.py**

```python
def fulltext_match_clause(dialect: str, column: str, keyword: str) -> str:
    if dialect == "sqlite":
        return f"{column} MATCH :kw"
    if dialect == "postgres":
        return f"to_tsvector({column}) @@ plainto_tsquery(:kw)"
    raise ValueError(f"unsupported dialect: {dialect}")
```

Run: `cd backend && pytest tests/test_sql_dialect.py -v`
Expected: PASS。

- [ ] **Step 3: 定义 Protocol 接口标注迁移点**

`base_repo.py`:

```python
from typing import Protocol

class Repository(Protocol):
    """所有 repo 的接口。切 Postgres 时需重新实现各方法的 SQL。
    迁移检查点:任何含 MATCH/FTS5/sqlite_master/AUTOINCREMENT 的查询。"""
    ...
```

在 `memory_repo.py` 的全文检索查询处,把硬编码的 `MATCH` 换成 `fulltext_match_clause(self._cm.dialect, ...)`,`ConnectionManager` 加 `self.dialect = "sqlite"` 属性。

- [ ] **Step 4: 跑表征 + 方言测试**

Run: `cd backend && pytest tests/test_database_facade_characterization.py tests/test_sql_dialect.py -v`
Expected: 全过(行为不变,只是把方言抽出来)。

- [ ] **Step 5: Commit**

```bash
git add backend/tars/database/repositories/base_repo.py backend/tars/database/sql_dialect.py backend/tars/database/repositories/memory_repo.py backend/tars/database/connection.py backend/tests/test_sql_dialect.py
git commit -m "refactor(db): introduce Repository protocol and dialect isolation seam for future Postgres"
```

---
# PHASE P2 — 放大差异化(产品化)

> 前提:`pip install "mcp[cli]"` 已加入 `backend/requirements.txt`(Task 10 Step 1 处理)。MCP server 复用 backend 的 `MemoryManager`/`EvolutionManager`,不重复造轮子。

## Task 10: memory MCP server

**Files:**
- Modify: `backend/requirements.txt`(加 `mcp[cli]`)
- Create: `mcp/tars_memory_server.py`
- Test: `backend/tests/test_memory_mcp.py`

复用真实方法:`MemoryManager.search_memories(query, limit)`、`add_manual_memory(content, category)`、`get_context_for_query(query, limit)`、`for_tenant(tenant_id)`。

- [ ] **Step 1: 加依赖**

在 `backend/requirements.txt` 追加一行 `mcp[cli]>=1.2.0`,然后:
Run: `cd backend && . venv/bin/activate && pip install "mcp[cli]>=1.2.0"`
Expected: 安装成功。

- [ ] **Step 2: 写测试(验证工具函数包装真实 manager)**

写入 `backend/tests/test_memory_mcp.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp"))
from tars_memory_server import _search_memory, _add_memory

def test_mcp_add_and_search(tmp_path, monkeypatch):
    monkeypatch.setenv("TARS_DATA_DIR", str(tmp_path))
    _add_memory(content="user prefers dark mode", category="user_preference", tenant="t")
    out = _search_memory(query="dark mode", tenant="t", limit=5)
    assert "dark mode" in out
```

Run: `cd backend && pytest tests/test_memory_mcp.py -v`
Expected: FAIL(模块不存在)。

- [ ] **Step 3: 实现 memory MCP server**

写入 `mcp/tars_memory_server.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from mcp.server.fastmcp import FastMCP
from tars.memory.manager import MemoryManager

mcp = FastMCP("tars-memory")
_mgr = MemoryManager()


def _search_memory(query: str, tenant: str = "default", limit: int = 5) -> str:
    hits = _mgr.for_tenant(tenant).search_memories(query, limit=limit)
    return "\n".join(getattr(h, "content", str(h)) for h in hits) or "(no results)"


def _add_memory(content: str, category: str = "fact", tenant: str = "default") -> str:
    import asyncio
    asyncio.run(_mgr.for_tenant(tenant).add_manual_memory(content, category=category))
    return "saved"


@mcp.tool()
def search_memory(query: str, tenant: str = "default", limit: int = 5) -> str:
    """检索 TARS 长期记忆。"""
    return _search_memory(query, tenant, limit)


@mcp.tool()
def add_memory(content: str, category: str = "fact", tenant: str = "default") -> str:
    """写入一条 TARS 记忆。"""
    return _add_memory(content, category, tenant)


if __name__ == "__main__":
    mcp.run()
```

Run: `cd backend && pytest tests/test_memory_mcp.py -v`
Expected: PASS(若 `MemoryManager()` 构造需参数,读 manager.py 第 1–40 行补上)。

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt mcp/tars_memory_server.py backend/tests/test_memory_mcp.py
git commit -m "feat(mcp): expose TARS memory as standalone MCP server"
```

---

## Task 11: Evolution dashboard API + 前端页

**Files:**
- Create: `backend/tars/api/evolution_metrics.py`
- Modify: `backend/tars/app_factory.py`(注册新路由)
- Create: `frontend/src/views/EvolutionDashboard.vue`
- Test: `backend/tests/test_evolution_metrics_api.py`

复用真实方法:`EvolutionManager.get_stats()`、`feedback_collector.count_recent(tenant_id, days)`。

- [ ] **Step 1: 写 API 测试**

写入 `backend/tests/test_evolution_metrics_api.py`:

```python
from fastapi.testclient import TestClient
from tars.main import app

def test_evolution_metrics_endpoint():
    client = TestClient(app)
    r = client.get("/api/evolution/metrics?tenant_id=default")
    assert r.status_code == 200
    body = r.json()
    assert "stats" in body and "recent_feedback" in body
```

Run: `cd backend && pytest tests/test_evolution_metrics_api.py -v`
Expected: FAIL(路由不存在)。

- [ ] **Step 2: 实现 metrics 路由**

写入 `backend/tars/api/evolution_metrics.py`:

```python
from fastapi import APIRouter
from tars.evolution.manager import EvolutionManager

router = APIRouter(prefix="/api/evolution", tags=["evolution"])
_mgr = EvolutionManager()


@router.get("/metrics")
def metrics(tenant_id: str = "default"):
    return {
        "stats": _mgr.get_stats(),
        "recent_feedback": _mgr.feedback_collector.count_recent(tenant_id, days=7),
    }
```

- [ ] **Step 3: 注册路由**

在 `backend/tars/app_factory.py` 的 `create_app()` 内,与其它 `include_router` 并列加:

```python
from tars.api import evolution_metrics
app.include_router(evolution_metrics.router)
```

Run: `cd backend && pytest tests/test_evolution_metrics_api.py -v`
Expected: PASS(若 `EvolutionManager()` 或 `get_stats()` 返回结构不同,读 manager.py 第 257 行对齐断言)。

- [ ] **Step 4: 前端 dashboard 页(最小可用)**

写入 `frontend/src/views/EvolutionDashboard.vue`:

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
const stats = ref<Record<string, unknown>>({})
const recent = ref(0)
onMounted(async () => {
  const r = await fetch('/api/evolution/metrics?tenant_id=default')
  const d = await r.json()
  stats.value = d.stats
  recent.value = d.recent_feedback
})
</script>

<template>
  <div class="p-4">
    <h2 class="text-lg font-bold">自进化指标</h2>
    <p>近 7 天反馈条数:{{ recent }}</p>
    <pre>{{ JSON.stringify(stats, null, 2) }}</pre>
  </div>
</template>
```

- [ ] **Step 5: 验证前端可构建**

Run: `cd frontend && npm run build 2>&1 | tail -5`
Expected: build 成功(新增页面不破坏构建)。**注:路由挂载到菜单需按现有 router 约定补一行,读 `frontend/src/router` 后追加。**

- [ ] **Step 6: Commit**

```bash
git add backend/tars/api/evolution_metrics.py backend/tars/app_factory.py frontend/src/views/EvolutionDashboard.vue backend/tests/test_evolution_metrics_api.py
git commit -m "feat(evolution): add metrics API and dashboard view for adoption/feedback visibility"
```

---

## 验收(全计划完成后)

- [ ] Gitee Go 流水线在 push 时绿灯(lint + test + 前端 build 全过)
- [ ] `wc -l backend/tars/database/base.py backend/tars/agent/agent.py backend/tars/main.py` — 三个文件均显著瘦身
- [ ] `cd backend && pytest -q` — 相对计划开始的基线**零新增失败**
- [ ] memory MCP server 可被 Claude/Cursor 等宿主接入(`python mcp/tars_memory_server.py` 不报错)
- [ ] `/api/evolution/metrics` 返回 stats + recent_feedback,前端 dashboard 可渲染

## 显式排除(YAGNI,本计划不做)

- ❌ 不实际迁移 Postgres / pgvector(仅留接口,见 Task 9)
- ❌ 不引入 Celery/RQ 任务队列(P1 原列项,但非本轮决策范围;长任务现状保留)
- ❌ 不重写 Chroma 向量层(已有 `vectorstore/chroma_client.py` 抽象,够用)
- ❌ evolution MCP server(Task 列出过,但 dashboard 已覆盖对外可见性需求,避免重复)

