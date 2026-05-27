---
doc_type: plan
status: shipped
platform_version: 4.3.1
catalog: docs/superpowers/README.md
---
# InsightForge 鉴数建档性能优化 — 实施计划（INS-2.1）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按 Task 逐步执行。步骤使用 `- [ ]` 跟踪进度。

**Goal:** 让 InsightForge Profile P2 统计阶段真正受 `InsightBudget` 约束：表级并行、SQL 超时、增量 reuse（含 sample 重抓 + LLM annotation 复用）、T1 批量列统计，并写入 `insight_snapshot.perf`。

**Architecture:** 在 `StatsCollector` 外包一层 async 并行调度；新增 fingerprint/planner 决定增量；方言层增加 batch SQL；`ProfilePipeline` 汇总 perf 并向后兼容 snapshot schema；`LlmSynthesizer` 支持 target_tables 精准送批。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy / asyncio / pytest

**Spec:** [2026-05-24-insightforge-profile-perf-design.md](../specs/2026-05-24-insightforge-profile-perf-design.md) (v2 reviewed)

**Tests:** [profile_perf_suite.yaml](../../../backend/tests/insight/profile_perf_suite.yaml)

**预期收益（详见 spec §5.5）：**
- 首跑：30 表 100–120s → 35–50s（**2.4–3.0×**）
- 二跑 incremental：100–120s → 6–10s（**10–18×**）
- 真实 80 表 MySQL 二跑：10 min → 30–90s

---

## 里程碑

| 里程碑 | 交付物 | 验收 |
|--------|--------|------|
| **M0 — 前置** | `latest_completed_for_datasource` + 显式连接池 sizing | store 单测；engine 连接数日志合规 |
| **M1 — 并行 + 超时 + perf** | `SqlTimeoutExecutor` + async `collect_all` + perf 骨架 | L1/L2 用例绿；30 表 fixture 加速 ≥ 1.8×（mock LLM） |
| **M2 — 增量建档（含 sample 重抓 + LLM reuse）** | `schema_fingerprint` + `incremental_planner` + JobRunner 注入 + LlmSynthesizer.target_tables | 2nd run `tables_reused` ≥ 80%；二跑 ≤ 10s |
| **M3 — 批量列 SQL** | `BatchColumnStatsDialect` mysql/pg/sqlite + fallback 路径 | SQL 计数降 ≥ 50%；fallback 可观测 |
| **M4 — 可观测 + 版本 + bench 实装** | `perf` 段、INS-2.1.0 bump、bench runner 真实实装、acceptance 脚本 | Docker smoke + bench gate 通过 |

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/config/insight.yaml` | Modify | 新增 `parallel_tables_max`, `column_stats_batch_size=10`, `incremental_resample_on_reuse`, `reuse_synthesize_annotation` |
| `backend/tars/insight/config.py` | Modify | `InsightBudget` 新字段（5 个） |
| `backend/tars/insight/sql_timeout.py` | Create | statement timeout 执行器（多方言） |
| `backend/tars/insight/schema_fingerprint.py` | Create | 表结构指纹 |
| `backend/tars/insight/incremental_planner.py` | Create | full/incremental 表计划 |
| `backend/tars/insight/perf_summary.py` | Create | phase / stats / synthesize perf 汇总 |
| `backend/tars/insight/stats_collector.py` | Modify | async 并行 + 显式连接池 + timeout + batch 集成 |
| `backend/tars/insight/dialects/batch_stats.py` | Create | 批量列 stats SQL（mysql/pg/sqlite） |
| `backend/tars/insight/dialects/base.py` | Modify | 注册 batch helper，新增 statement_timeout hook |
| `backend/tars/insight/profile_pipeline.py` | Modify | previous_snapshot、perf、incremental 元数据、LLM target_tables |
| `backend/tars/insight/llm_synthesizer.py` | Modify | 支持 `target_tables=`，跳过 reuse 表 |
| `backend/tars/insight/job_runner.py` | Modify | 加载 previous completed snapshot；传 force |
| `backend/tars/insight/store.py` | Modify | **新增 `latest_completed_for_datasource`** |
| `backend/tars/insight/version.py` | Modify | `INS_VERSION = "INS-2.1.0"` |
| `backend/tests/insight/fixtures/profile_perf_db.py` | Modify | 加 `build_sqlite_with_drift()`（用于 sample 漂移测试） |
| `backend/tests/insight/profile_perf_suite.yaml` | Modify | 阈值 + 新增 sample 重抓 / LLM reuse 用例 |
| `backend/tests/insight/profile_perf_runner.py` | Modify | bench 路径真实实装；新模块路径接线 |
| `backend/tests/insight/test_insight_profile_perf_suite.py` | 保留 | 入口不变 |
| `backend/tests/test_insight_schema_fingerprint.py` | Create | 指纹单测 |
| `backend/tests/test_insight_incremental_planner.py` | Create | 增量规划单测 |
| `backend/tests/test_insight_sql_timeout.py` | Create | 超时单测 |
| `backend/tests/test_insight_batch_stats_dialect.py` | Create | 批量 SQL 单测 |
| `backend/tests/test_insight_run_store_latest_completed.py` | Create | store 新方法单测 |
| `backend/tests/test_insight_profile_pipeline.py` | Modify | 增量 e2e + sample 重抓 + LLM reuse |
| `scripts/acceptance/insightforge-profile-perf.sh` | Create | 人工验收 |

---

## Phase 0 — 前置（M0，必须先做）

### Task 0a: `InsightProfileRunStore.latest_completed_for_datasource`

**Files:**
- Modify: `backend/tars/insight/store.py`
- Test: `backend/tests/test_insight_run_store_latest_completed.py`

- [ ] **Step 1: 写测试**

```python
def test_latest_completed_excludes_pending_failed(db):
    store = InsightProfileRunStore(db)
    r1 = store.create("ds1", "default", "INS-2.0.0", {})
    store.complete(r1.id, "default", status="failed")
    r2 = store.create("ds1", "default", "INS-2.0.0", {})
    store.complete(r2.id, "default", status="completed", insight_snapshot={"tables": {"t1": {}}})
    latest = store.latest_completed_for_datasource("ds1", "default")
    assert latest.id == r2.id
    assert latest.insight_snapshot_json["tables"] == {"t1": {}}

def test_latest_completed_returns_none_when_no_completed(db):
    store = InsightProfileRunStore(db)
    r = store.create("ds2", "default", "INS-2.0.0", {})
    assert store.latest_completed_for_datasource("ds2") is None
```

- [ ] **Step 2: 实现**

```python
def latest_completed_for_datasource(self, datasource_id, tenant_id="default"):
    cur = self.db._get_conn().cursor()
    cur.execute("""
        SELECT * FROM insight_profile_runs
        WHERE datasource_id = ? AND tenant_id = ? AND status = 'completed'
        ORDER BY finished_at DESC LIMIT 1
    """, (datasource_id, tenant_id))
    return self._row_to_run(cur.fetchone())
```

- [ ] **Step 3: PASS + commit**

---

### Task 0b: 显式连接池 sizing

**Files:**
- Modify: `backend/tars/insight/stats_collector.py::_engine_get`
- Test: `backend/tests/test_insight_stats_collector_pool.py`（新建，仅 1 用例）

- [ ] **Step 1: 测试**

```python
def test_engine_pool_size_scales_with_parallel(tmp_path):
    url = f"sqlite:///{tmp_path}/a.db"
    budget = InsightBudget(parallel_tables=5)
    sc = StatsCollector(url, "sqlite", "sqlite", budget)
    engine = sc._engine_get()
    # SQLite 用 SingletonThreadPool / StaticPool — 至少不报错；MySQL/PG 走 QueuePool
    assert engine is not None
    sc.close()
```

- [ ] **Step 2: 实现** — 仅对非 sqlite URL 设置 `pool_size = max(parallel+2, 5)`, `max_overflow = max(parallel, 5)`, `pool_pre_ping=True`

- [ ] **Step 3: PASS + commit**

---

## Phase 1 — SQL 超时与 perf 骨架（M1）

### Task 1: SqlTimeoutExecutor

**Files:**
- Create: `backend/tars/insight/sql_timeout.py`
- Test: `backend/tests/test_insight_sql_timeout.py`

- [ ] **Step 1: 写失败测试（修订：必须能真正 FAIL）**

```python
def test_sqlite_slow_query_returns_none(tmp_path):
    """SQLite 不能取消 SELECT；执行器必须用 future timeout 兜底。"""
    from tars.insight.sql_timeout import SqlTimeoutExecutor
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{tmp_path}/t.db")
    # 用 SQL CTE 制造 ~3s 自循环
    slow_sql = """
        WITH RECURSIVE cnt(x) AS (
          SELECT 1 UNION ALL SELECT x+1 FROM cnt WHERE x < 5000000
        ) SELECT COUNT(*) FROM cnt
    """
    exec_ = SqlTimeoutExecutor(timeout_sec=1)
    t0 = time.time()
    result = exec_.fetch_one(engine, slow_sql)
    elapsed = time.time() - t0
    assert result is None  # 超时返回 None
    assert elapsed < 2.0   # 必须在 1s 后立即返回（容忍 1s 抖动）

def test_fast_query_succeeds():
    ...  # 反向用例
```

- [ ] **Step 2: 运行确认 FAIL**

Run: `cd backend && pytest tests/test_insight_sql_timeout.py -v`

- [ ] **Step 3: 实现 `SqlTimeoutExecutor`**

```python
class SqlTimeoutExecutor:
    def __init__(self, timeout_sec: int = 15, dialect: str = "generic"): ...
    def fetch_one(self, engine, sql: str, params=None) -> Any | None:
        """Returns None on timeout (caller records quality_flag)."""
    def fetch_all(self, engine, sql: str, params=None) -> list | None: ...
```

实现要点：
- PG: `BEGIN; SET LOCAL statement_timeout='15000'; <sql>; COMMIT`
- MySQL/Doris: 在 SELECT 前注入 `/*+ MAX_EXECUTION_TIME(15000) */`
- SQLite/Generic: `concurrent.futures.ThreadPoolExecutor` + `future.result(timeout=...)`

- [ ] **Step 4: PASS + commit**

---

### Task 2: perf_summary 与 pipeline 计时

**Files:**
- Create: `backend/tars/insight/perf_summary.py`
- Modify: `backend/tars/insight/profile_pipeline.py`
- Test: `backend/tests/test_insight_profile_pipeline.py`（新增 `test_profile_snapshot_includes_perf`）

- [ ] **Step 1: 写失败测试**

```python
async def test_profile_snapshot_includes_perf(tmp_path):
    # 建 3 表 sqlite → run → assert perf 段
    result = await pipeline.run(ds)
    snap = result["insight_snapshot"]
    assert "perf" in snap
    assert snap["perf"]["phases_ms"]["stats"] > 0
    assert snap["perf"]["stats"]["tables_total"] == 3
    assert snap["perf"]["total_ms"] >= snap["perf"]["phases_ms"]["stats"]
```

- [ ] **Step 2: 实现 `ProfilePerfTracker`** — context manager + `mark_phase(name)` + `inc_counter(key, n=1)`

- [ ] **Step 3: `ProfilePipeline.run` 各 phase 前后 `tracker.mark`,counter 自 StatsCollector 反向回传**

- [ ] **Step 4: PASS + commit**

---

## Phase 2 — 表级并行（M1）

### Task 3: async collect_all

**Files:**
- Modify: `backend/tars/insight/stats_collector.py`
- Test: `backend/tests/insight/profile_perf_suite.yaml` 中 `parallel_respects_semaphore`、`parallel_sqlite_serial`

- [ ] **Step 1: suite 用例已存在（profile_perf_suite.yaml 行 203-237），先跑确认 skip**

```bash
pytest tests/insight/test_insight_profile_perf_suite.py -v -k parallel
# 应全部 skip："collect_all_async not implemented"
```

- [ ] **Step 2: 实现 `collect_all_async`**

```python
async def collect_all_async(
    self, schema, table_names=None, *, track_concurrency=False
) -> tuple[dict[str, TableStats], dict]:
    engine = self._engine_get()
    helper = get_dialect_helper(engine, self.stats_dialect, self.db_type)
    ordered_tables = self._rank_tables(schema, helper, table_names)
    sem = asyncio.Semaphore(self._effective_parallelism())
    inflight = 0
    max_inflight = 0
    lock = asyncio.Lock()

    async def one(table):
        nonlocal inflight, max_inflight
        async with sem:
            if track_concurrency:
                async with lock:
                    inflight += 1; max_inflight = max(max_inflight, inflight)
            try:
                tdef = (schema.get("tables") or {}).get(table) or {}
                return table, await asyncio.to_thread(
                    self.collect_table, engine, helper, table, tdef.get("columns") or []
                )
            finally:
                if track_concurrency:
                    async with lock:
                        inflight -= 1

    pairs = await asyncio.gather(*[one(t) for t in ordered_tables], return_exceptions=True)
    out: dict[str, TableStats] = {}
    quality_flags = []
    for entry in pairs:
        if isinstance(entry, Exception):
            quality_flags.append({"issue": "table_collect_error", "detail": str(entry)[:200]})
            continue
        t, ts = entry
        out[t] = ts
    return out, {"max_inflight": max_inflight, "quality_flags": quality_flags}
```

- [ ] **Step 3: `_effective_parallelism()`** — sqlite → 1；clamp 到 `parallel_tables_max`

- [ ] **Step 4: `ProfilePipeline` 改调 `await collector.collect_all_async`,quality_flags 合并到顶层**

- [ ] **Step 5: PASS + commit**

---

### Task 4: 集成 SqlTimeout 到列统计

**Files:**
- Modify: `backend/tars/insight/stats_collector.py::_collect_column`
- Test: `backend/tests/test_insight_sql_timeout.py::test_slow_column_records_quality_flag`

- [ ] **Step 1: 失败测试 — 用 SQLite CTE 模拟慢列,断言:**
  - `cstats.null_rate is None`
  - 顶层 `quality_flags` 含 `{"table": ..., "column": ..., "issue": "stats_timeout"}`

- [ ] **Step 2: 实现 — `_collect_column` 调用 `SqlTimeoutExecutor`,超时 return ColumnStats 并通过返回值携带 flag**

- [ ] **Step 3: 表级 wall timeout — `collect_table` 循环开头检查 `time.time() - start > budget.table_timeout_sec`,跳出剩余列并记 `skipped_reason="table_timeout"`**

- [ ] **Step 4: PASS + commit**

---

## Phase 3 — 增量建档（M2）

### Task 5: SchemaFingerprint

**Files:**
- Create: `backend/tars/insight/schema_fingerprint.py`
- Test: `backend/tests/test_insight_schema_fingerprint.py`

- [ ] **Step 1: 测试**

```python
def test_fingerprint_stable_for_same_schema(): ...
def test_fingerprint_changes_when_column_added(): ...
def test_fingerprint_changes_when_column_type_changed(): ...
def test_fingerprint_ignores_column_comment(): ...
def test_fingerprint_ignores_column_order(): ...
def test_fingerprint_includes_primary_key(): ...
```

- [ ] **Step 2: 实现 `fingerprint_table` / `fingerprint_schema`**

- [ ] **Step 3: PASS + commit**

---

### Task 6: IncrementalPlanner

**Files:**
- Create: `backend/tars/insight/incremental_planner.py`
- Test: `backend/tests/test_insight_incremental_planner.py`

- [ ] **Step 1: 测试矩阵（覆盖 profile_perf_suite.yaml 的 6 个 planner 用例）**

| case | expect |
|------|--------|
| force=True | all collect |
| enable_incremental=False | all collect |
| no previous | all collect |
| previous TTL expired | all collect（TTL 过期 → fp 不再可信） |
| unchanged 5 tables | 5 reuse |
| 1 new table | 1 collect + N reuse |
| dropped table | action drop |
| column added 1 table | 1 collect + N-1 reuse |

- [ ] **Step 2: 实现 `IncrementalPlanner.plan(schema, previous_snapshot, *, force=False)` 返回 `Plan(actions, reused_count, collected_count, dropped_count, profile_run_type)`**

- [ ] **Step 3: PASS + commit**

---

### Task 7: Pipeline + JobRunner 接线（含 sample 重抓）

**Files:**
- Modify: `backend/tars/insight/profile_pipeline.py`
- Modify: `backend/tars/insight/job_runner.py`
- Modify: `backend/tars/insight/sampler.py`（暴露 batch sample API）
- Test: `backend/tests/test_insight_profile_pipeline.py::test_incremental_reuses_tables_and_resamples`

- [ ] **Step 1: 测试断言**

```python
async def test_incremental_reuses_stats_but_resamples(tmp_path):
    pipeline = ProfilePipeline(llm_provider=None)
    # 第一次跑
    r1 = await pipeline.run(ds)
    s1 = r1["insight_snapshot"]
    t0_sample = s1["tables"]["t_0"]["sample_rows"]

    # 向 t_0 插入新数据,但 schema 不变
    insert_more_rows(db_file, "t_0")

    # 第二次跑（带 previous）
    r2 = await pipeline.run(ds, previous_snapshot=s1)
    s2 = r2["insight_snapshot"]
    assert s2["profile_run_type"] == "incremental"
    assert s2["incremental"]["reused"] >= 1
    assert s2["incremental"]["resampled"] >= 1
    # sample 必须变化（行数变了）
    t1_sample = s2["tables"]["t_0"]["sample_rows"]
    assert len(t1_sample) >= 1
    # stats 复用（null_rate 字段存在但来自 previous）
    assert s2["tables"]["t_0"]["columns"]["id"]["distinct_count"] == \
           s1["tables"]["t_0"]["columns"]["id"]["distinct_count"]
```

- [ ] **Step 2: `ProfilePipeline.run(..., previous_snapshot=None, force=False)`**

- [ ] **Step 3: reuse 分支**

```python
for table, action in plan.actions.items():
    if action == "reuse":
        prev_ts = TableStats.from_dict(previous_snapshot["tables"][table])
        if budget.incremental_resample_on_reuse:
            prev_ts.sample_rows = fetch_sample_rows(engine, table, ..., dialect, db_type)
        table_stats[table] = prev_ts
```

- [ ] **Step 4: `insight_snapshot.profile_run_type` / `incremental.{reused, collected, dropped, resampled}` 写入**

- [ ] **Step 5: JobRunner — 调用 `self.run_store.latest_completed_for_datasource(datasource_id, tenant_id)`,把 `insight_snapshot_json` 传给 `pipeline.run(previous_snapshot=..., force=(run.budget_json.get("force") is True))`**

- [ ] **Step 6: PASS + commit**

---

### Task 7b: LLM Synthesize 增量复用（spec §4.6 新增）

**Files:**
- Modify: `backend/tars/insight/llm_synthesizer.py`
- Modify: `backend/tars/insight/profile_pipeline.py`
- Test: `backend/tests/test_insight_profile_pipeline.py::test_llm_annotation_reused_on_incremental`

- [ ] **Step 1: 测试**

```python
async def test_llm_annotation_reused_on_incremental(tmp_path, monkeypatch):
    call_count = {"n": 0}
    class CountingLlm:
        async def chat(self, *a, **kw):
            call_count["n"] += 1
            return {"content": '{"description":"mock"}'}
    pipeline = ProfilePipeline(llm_provider=CountingLlm())
    r1 = await pipeline.run(ds)
    n1 = call_count["n"]
    r2 = await pipeline.run(ds, previous_snapshot=r1["insight_snapshot"])
    n2 = call_count["n"] - n1
    assert n2 == 0  # schema 不变 → annotation 全 reuse → LLM 完全不调
```

- [ ] **Step 2: `LlmSynthesizer.synthesize(..., target_tables: list[str] | None = None)` — None 表示全量;否则仅对 target_tables 调 LLM**

- [ ] **Step 3: pipeline 计算 `synthesize_targets = [t for t in tables if plan.actions[t] == "collect"]`**

- [ ] **Step 4: previous_snapshot 的 `schema_annotations` 拷贝到当前 `annotations` 字典(reuse 部分)**

- [ ] **Step 5: perf.synthesize 写入 `{tables_llm, tables_annotation_reused, batches_sent}`**

- [ ] **Step 6: PASS + commit**

---

## Phase 4 — 批量列 SQL（M3）

### Task 8: BatchColumnStatsDialect

**Files:**
- Create: `backend/tars/insight/dialects/batch_stats.py`
- Modify: `backend/tars/insight/dialects/base.py`
- Modify: `backend/tars/insight/stats_collector.py::collect_table`
- Test: `backend/tests/test_insight_batch_stats_dialect.py` + `profile_perf_suite.yaml::batch_*`

- [ ] **Step 1: 测试**
  - SQL shape: 含 `COUNT(*)`, 每列一个 `COUNT(DISTINCT)`, 每列一个 `SUM(... IS NULL)`
  - 列数 ≤ `column_stats_batch_size`
  - SQL 长度 < 8000 chars（保护极宽表）
  - PG 大表自动退到单列（mock helper.estimate_row_count > 100000）

- [ ] **Step 2: 实现 `build_batch_stats_sql(table, columns, dialect)` + `parse_batch_result(row, columns)`**

- [ ] **Step 3: `collect_table` 优先 batch；任一异常 → fallback 单列循环 + `quality_flags.append({issue: "batch_fallback"})`**

- [ ] **Step 4: perf 计数 `sql_executed` / `sql_batch_used` / `sql_fallback_single`**

- [ ] **Step 5: PASS + commit**

---

## Phase 5 — 测试套件与验收（M4）

### Task 9: profile_perf_runner 实装 bench

**Files:**
- Modify: `backend/tests/insight/profile_perf_runner.py`
- Modify: `backend/tests/insight/profile_perf_suite.yaml`（阈值调整）
- Modify: `backend/tests/insight/fixtures/profile_perf_db.py`（加 `insert_extra_rows`）

- [ ] **Step 1: bench runner 实装 — `run_bench_case` 不再 skip**

```python
def run_bench_case(case: dict, tmp_path: Path) -> None:
    _requires_bench(case)
    setup = case.get("setup") or {}
    if case["action"] == "bench_run":
        db_file = tmp_path / "bench.db"
        url = build_sqlite(db_file, n_tables=setup["n_tables"],
                          n_columns=setup.get("n_columns", 10), n_rows=200)
        budget = InsightBudget(parallel_tables=setup.get("parallel_tables", 3))
        # build ds, run pipeline with mock LLM, measure wall time
        ...
        assert wall_time <= case["expect"]["wall_time_sec_lte"], \
            f"wall {wall_time:.1f}s > {case['expect']['wall_time_sec_lte']}s"
        if "speedup_vs_serial_gte" in case["expect"]:
            # 同 fixture 跑 parallel_tables=1 拿基线
            ...
            assert speedup >= case["expect"]["speedup_vs_serial_gte"]
```

- [ ] **Step 2: `bench_run_twice` — 跑两次,二次带 previous_snapshot**

- [ ] **Step 3: `bench_sql_count` — 通过 SQLAlchemy event 钩子 `before_cursor_execute` 计数,对比 batch on/off**

- [ ] **Step 4: 添加 fixture util**

```python
# fixtures/profile_perf_db.py
def insert_extra_rows(path, table: str, n: int = 100): ...
def alter_add_column(path, table: str, col: str, dtype: str = "TEXT"): ...
```

- [ ] **Step 5: 跑 `INSIGHT_PERF_BENCH=1 pytest -m insight_perf -v` 确认全绿**

---

### Task 10: 版本 bump + acceptance + 文档

**Files:**
- Modify: `backend/tars/insight/version.py` → `INS_VERSION = "INS-2.1.0"`
- Modify: `backend/config/insight.yaml` → `version: INS-2.1.0`
- Create: `scripts/acceptance/insightforge-profile-perf.sh`
- Modify: `docs/03-实施计划/roadmap.md`（一行 INS-2.1）

- [ ] **Step 1: bump 版本**

- [ ] **Step 2: acceptance 脚本**

```bash
#!/usr/bin/env bash
# 启动 backend,forge demo ds,断言 perf 字段存在 & total_ms 在阈值内
set -euo pipefail
PERF_THRESHOLD_MS=${PERF_THRESHOLD_MS:-60000}
# ... uvicorn boot + curl POST /insight/datasources/{ds}/profile/start + poll until completed
# ... jq '.insight_snapshot.perf.total_ms' must be < $PERF_THRESHOLD_MS
```

- [ ] **Step 3: commit**

---

## 验证命令（完整）

```bash
# 单元 + 集成（不含 bench）
cd backend && pytest \
  tests/test_insight_run_store_latest_completed.py \
  tests/test_insight_stats_collector_pool.py \
  tests/test_insight_schema_fingerprint.py \
  tests/test_insight_incremental_planner.py \
  tests/test_insight_sql_timeout.py \
  tests/test_insight_batch_stats_dialect.py \
  tests/test_insight_profile_pipeline.py \
  tests/insight/test_insight_profile_perf_suite.py \
  -v -m "not insight_perf"

# 性能基准（本地）
INSIGHT_PERF_BENCH=1 pytest tests/insight/test_insight_profile_perf_suite.py -v -m insight_perf

# Docker 烟测（可选）
INSIGHT_DOCKER_TEST=1 pytest tests/test_insight_docker_smoke.py::test_profile_mysql_pipeline -v

# 完整回归（确认未破坏 INS-2.0）
cd backend && pytest tests/test_insight_*.py tests/insight/ -v
```

---

## 回滚预案

任何 milestone 不达预期,可通过 yaml 关闭对应特性:

| 特性 | 回滚开关 |
|------|---------|
| 表级并行 | `profile.parallel_tables: 1` |
| 增量 | `profile.enable_incremental: false` |
| 批量 SQL | `TARS_INSIGHT_DISABLE_BATCH_SQL=1`（环境变量） |
| LLM annotation reuse | `profile.reuse_synthesize_annotation: false` |

关闭后行为应**完全等价于 INS-2.0**。Task 9 bench 必须有一个用例验证"全部回滚"场景下与 INS-2.0 baseline 偏差 < 5%。

---

## Self-Review（Spec v2 覆盖）

| Spec § | Task |
|--------|------|
| §4.1 并行 + 显式连接池 | Task 0b, 3 |
| §4.2 超时（含 SQLite 修正） | Task 1, 4 |
| §4.3 批量 SQL（batch_size=10） | Task 8 |
| §4.4 增量 + sample 重抓 | Task 0a, 5, 6, 7 |
| §4.5 perf 段 | Task 2 |
| **§4.6 LLM annotation reuse** | **Task 7b**（v1 缺失，v2 补齐） |
| §5 配置 5 项 | Task 0a/8/7/7b 散落 |
| §7 测试阈值 | Task 9 |
| §8 里程碑 M0–M4 | 全部 |

---

**Plan v2 complete.** 关键差异(v1 → v2):

- 新增 **Phase 0**(M0 前置 — `latest_completed_for_datasource` + 连接池 sizing)
- 新增 **Task 7b** — LLM annotation 增量复用,这是二跑加速比从 3× 提到 10× 的关键
- 修订 Task 1 测试用例为可真正 FAIL 的 CTE 慢查询
- Task 8 加 PG 大表自动 fallback、SQL 长度保护
- Task 9 bench runner 不再 skip,真实实装
- 加回滚预案表

执行选项:

1. **Subagent-Driven（推荐）** — 每 Task 独立 subagent + 阶段 review
2. **Inline Execution** — 本会话按 Task 顺序实现，M1 完成后 checkpoint
