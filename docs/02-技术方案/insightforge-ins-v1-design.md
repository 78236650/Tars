# InsightForge 鉴数 — 技术详设 INS-1.0.0

> **能力 Tag**: `@insight-forge`  
> **版本**: `INS-1.0.0`  
> **关联**: [产品架构设计](../superpowers/specs/2026-05-19-insightforge-design.md)

---

## 1. 技术目标

1. **可落地**: 仅依赖 TARS 已有 `bi` + `knowledge` + `SQLAlchemy`，不引入 DataHub。
2. **性能可控**: 全链路 `InsightBudget` 限流；SQL 优先于 Pandas。
3. **可测试**: 每阶段纯函数 + SQLite fixture 库集成测试。
4. **可演进**: `insight_snapshot` schema 带 `schema_version`，支持 INS-1.1 增量字段。
5. **数据库**: Oracle / MySQL / PostgreSQL 一等方言；JDBC 走 `GenericStatsDialect` 降级（评审已定稿）。
6. **可视化边界**: `insight` 模块无图表 API；原型图由平台 `python_exec` 承担（评审已定稿）。

---

## 2. 组件详设

### 2.1 `stats_collector.py`

**职责**: 对单表生成列级统计，不写 LLM。

**输入**: `connection_url`, `table_name`, `columns[]`, `InsightBudget`

**输出** `TableStats`:

```python
@dataclass
class ColumnStats:
    name: str
    db_type: str
    null_rate: float | None
    distinct_count: int | None
    distinct_rate: float | None
    min_value: str | None
    max_value: str | None
    sample_values: list[str]  # max 5
    enum_top: list[dict]        # [{value, count}] max 10

@dataclass
class TableStats:
    table: str
    row_estimate: int
    columns: dict[str, ColumnStats]
    elapsed_ms: int
    skipped_reason: str | None
```

**方言分层（评审已定稿）**:

| Tier | `db_type` | Profile 统计 | Metric QA |
|------|-----------|----------------|-----------|
| **T1** | `oracle`, `mysql`, `postgresql`, `doris` | 完整方言 SQL（doris 复用 MySQL 统计实现） | 完整 |
| **T2** | `jdbc`（及未单独优化的方言） | `GenericStatsDialect` | 只读查询 + 基础采样 |
| **T1 扩展** | `sqlserver`, `clickhouse` | 与 BI 模块共用，按方言表实现 | 同 T1 |

**SQL 策略（T1 按 dialect 分支）**:

| 统计 | MySQL | PostgreSQL | Oracle |
|------|-------|------------|--------|
| 行数 | `TABLE_ROWS` 或采样 `COUNT(*)` | `reltuples` 或 `COUNT(*)` | `NUM_ROWS`（`ALL_TABLES`）或采样 |
| null_rate | `SUM(col IS NULL)/COUNT(*)` | 同左 | 同左 |
| distinct | `COUNT(DISTINCT col)`（大表加子查询 LIMIT） | 同左 | 同左 |
| 采样 | `ORDER BY RAND() LIMIT N` | `TABLESAMPLE` / `random()` | `SAMPLE(n)` 或 `DBMS_RANDOM` |
| （Doris） | 同 MySQL 列 | — | `information_schema` + `ORDER BY RAND()` |

**Doris 说明**: FE 使用 MySQL  wire 协议；`db_type=doris` 时 `stats_collector` 委托 `MysqlStatsDialect`，连接 URL 仍为 `mysql+pymysql://user:pass@fe_host:9030/db`。

**`GenericStatsDialect`（T2 / JDBC）**:

- 仅保证：`SELECT COUNT(*)`, 列级 `NULL` 计数, `ORDER BY 1` 不支持时改用主键范围抽样  
- 跳过：方言专属 `TABLESAMPLE`、`APPROX_COUNT_DISTINCT`  
- 日志标记：`profile_mode=generic`

**超时**: 单 SQL `stats_timeout_sec`；超时则该列 `null_rate=None` 并记 `quality_flags`。

---

### 2.2 `relation_inferencer.py`

**职责**: 输出 `RelationEdge[]`。

**规则优先级**:

1. **P1 声明 FK** — `SchemaExplorer` 已有 → `confidence=1.0`, `type=fk_declared`
2. **P2 命名启发** — `{table}_id` → `table.id`，类型兼容 → `confidence=0.6`, `type=naming_guess`
3. **P3 值域重叠** — 仅 `core` 表对；抽样 500 行算 `|A∩B|/|A|` → `confidence=min(0.95, ratio)`, `type=value_overlap`

**上限**: 每数据源最多评估 `max_relation_pairs=200` 对，防止 O(n²) 爆炸。

```python
@dataclass
class RelationEdge:
    from_ref: str   # orders.user_id
    to_ref: str     # users.id
    type: str
    confidence: float
    evidence: str   # 人类可读
```

---

### 2.3 `role_classifier.py`

**职责**: 无 LLM 表角色分类（借鉴 datasculpt 思路）。

| 角色 | 规则示例 |
|------|----------|
| `fact` | 行数大 + 含度量列 + 含时间列 |
| `dimension` | 行数中 + 高 distinct 列少 + 被 FK 指向多 |
| `bridge` | 仅复合主键、两列均为 FK |
| `config` | 行数 <500 + 无时间列 |
| `log` | 表名含 `log`/`event`/`audit` |

输出写入 `insight_snapshot.table_tiers`。

---

### 2.4 `llm_synthesizer.py`

**职责**: 批量表 → 结构化 JSON。

**输入 token 控制**:

- 每表最多 20 列进入 prompt
- 统计只保留：null_rate, distinct_rate, sample_values, enum_top 前 3
- relations 只保留 confidence ≥ 0.6

**输出 JSON Schema**（节选）:

```json
{
  "tables": {
    "orders": {
      "business_name": "订单事实表",
      "description": "...",
      "columns": {
        "amount": {"label": "订单金额", "unit": "元"}
      }
    }
  },
  "metric_candidates": [
    {
      "key": "gmv_daily",
      "display_name": "日GMV",
      "definition": "...",
      "sql_template": "SELECT ...",
      "confidence": 0.85
    }
  ],
  "open_questions": ["status 字段枚举 3 的业务含义待确认"]
}
```

**失败**: JSON 解析失败 → 重试 1 次（temperature=0）；仍失败 → 该 batch 标记 `partial`，不阻塞 P5。

**落库**:

- `tables.*` → `schema_annotations`
- `metric_candidates` → `insight_metrics`（status=`draft`）

---

### 2.5 `knowledge_publisher.py`

**职责**: 渲染 Markdown + 调用 `KnowledgeIndexer`。

**文档结构（固定 TOC）**:

1. 数据源概览  
2. 实体关系图（Mermaid erDiagram）  
3. 核心表说明  
4. 指标候选清单  
5. 数据质量告警  
6. 待业务确认项  

**幂等**: 同 `datasource_id` 新 profile 时，删除旧 doc_id 向量（soft delete 或 overwrite 同 `doc_id` 前缀）。

---

### 2.6 `metric_qa_engine.py`

**职责**: `POST /ask` 的编排，可不经过完整 Agent Loop（降低延迟）。

```python
class MetricQaEngine:
    async def ask(
        self,
        datasource_id: str,
        tenant_id: str,
        question: str,
        as_of_date: date | None,
    ) -> MetricQaResult:
        ...
```

**步骤**:

1. `KnowledgeRetriever.search(question, collection=insight_{id}, filter={tars.capability: insight-forge})`
2. `InsightMetricStore.find_by_question` — embedding 或 keyword 匹配 `metric_key`
3. 若命中 `approved` metric → 填充 `sql_template` 参数执行
4. 否则若 `allow_ad_hoc_sql` → 调 LLM + `SQLAgent.execute_with_retry`
5. 组装 `MetricQaResult`

```python
@dataclass
class MetricQaResult:
    value: Any
    unit: str | None
    definition: str
    sql: str
    metric_id: str | None
    citations: list[str]
    open_questions: list[str]
```

---

### 2.7 `job_runner.py`

**职责**: 异步任务生命周期。

```python
class InsightJobRunner:
    async def start_profile(self, run_id: str) -> None: ...
    async def cancel(self, run_id: str) -> bool: ...

    def _update_progress(self, run_id, phase: str, current: int, total: int, message: str): ...
```

**并发**: `asyncio.Semaphore(parallel_tables)` 控制表级并行。

**持久化**: 每 phase 结束写 `progress_json`；支持前端 2s 轮询。

**进程模型**: INS-1.0 使用 FastAPI `BackgroundTasks`；INS-1.1 可选 Redis Queue。

---

## 3. 与 Agent 集成

### 3.1 自动知识检索增强

在 `Agent._build_knowledge_context` 增加：当 `session.metadata.role == insight_analyst` 或 `datasource_id` 存在时：

```python
filter_metadata = {"tars.capability": "insight-forge"}
if datasource_id:
    filter_metadata["datasource_id"] = datasource_id
```

### 3.2 Chat Session 元数据

```json
{
  "insight_mode": true,
  "datasource_id": "uuid",
  "capability_version": "INS-1.0.0"
}
```

前端从 `/insight` 跳转 Chat 时写入。

---

## 4. 配置与特性开关

`backend/tars/insight/version.py`:

```python
CAPABILITY_NAME = "insight-forge"
INS_VERSION = "INS-1.0.0"
INS_API_VERSION = 1  # 破坏性变更时 +1
```

环境变量覆盖:

| 变量 | 说明 |
|------|------|
| `TARS_INSIGHT_ENABLED` | `1/0` 覆盖 modules.yaml |
| `TARS_INSIGHT_MAX_TABLES` | 紧急限流 |

---

## 5. 数据库迁移

文件: `backend/migrations/00x_insight_forge.sql`

- `insight_profile_runs`
- `insight_metrics`
- 索引见产品文档 §6

**不回溯修改** `bi_datasources` 表结构；`insight` 子树存在 `schema_snapshot` JSON 内。

---

## 6. 测试策略

| 层级 | 内容 |
|------|------|
| 单元 | `role_classifier`, `relation_inferencer` 纯函数 |
| 集成 | SQLite 种子库 10 表 profile 全流程 |
| 契约 | API OpenAPI snapshot |
| 安全 | 拒绝 INSERT；超时 SQL |
| 回归 | 5 道 golden questions → 固定 SQL hash（approved metrics） |

`tests/test_insight_profile.py`  
`tests/test_insight_metric_qa.py`  
`tests/test_insight_security.py`

---

## 7. 可观测性

日志前缀: `[InsightForge/INS-1.0.0]`

结构化字段:

```json
{
  "capability": "insight-forge",
  "ins_version": "INS-1.0.0",
  "run_id": "...",
  "datasource_id": "...",
  "phase": "stats",
  "table": "orders",
  "elapsed_ms": 1200
}
```

Metrics（可选 Prometheus）:

- `insight_profile_duration_seconds`
- `insight_profile_tables_total`
- `insight_ask_duration_seconds`
- `insight_ask_errors_total`

---

## 8. INS-1.0.0 不实现项（明确排除）

- **模块内**图表 / 正式报表 UI（原型图 → 平台 `python_exec`，见产品文档 §3.4）  
- OpenMetadata 双向同步  
- 实时 CDC 增量  
- 多数据源联邦 JOIN  
- 自动写回业务库  

---

## 9. `python_exec` 协作（Session 上下文）

INS 不实现绘图；Metric QA 完成后可向 Session 写入供下游工具消费：

```python
# session.metadata（示例）
{
  "insight_last": {
    "datasource_id": "...",
    "question": "...",
    "value": 12345.67,
    "sql": "SELECT ...",
    "metric_id": "gmv_daily",
    "at": "2026-05-19T12:00:00+08:00"
  }
}
```

`analyst` / `developer` 角色调用 `python_exec` 时，System Prompt 追加：优先使用 `insight_last.sql` 结果，勿重复造口径。

审计：`insight_ask` 与 `python_exec` 分 action，便于区分鉴数 vs 原型。

---

## 10. JDBC 接入约定

1. 运维在 `bi_datasources` 登记 `db_type=jdbc`（或具体别名映射到桥接 URL）。  
2. `connection_url` 由部署方提供（内部 JDBC 网关 / SQLAlchemy 兼容桥）。  
3. 连接测试沿用 `SchemaExplorer.test_connection()`。  
4. Profile 启动时若 `db_type` 非 T1，自动 `profile_mode=generic` 并 UI 提示「基础鉴数模式」。  

驱动与 URL 模板写入 `docs/04-运维文档/insightforge-databases.md`（实施 Phase 4 补充）。

---

*技术详设 INS-1.0.0 — 评审通过 2026-05-19。*
