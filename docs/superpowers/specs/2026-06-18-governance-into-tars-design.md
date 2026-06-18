# 数据治理融入 TARS — 阶段0+阶段1 设计

> 日期：2026-06-18
> 状态：设计已确认，待写实施计划
> 上游决策：`docs/superpowers/specs/2026-06-18-argus-tars-fusion-strategy.md`（融合战略）
> 实施方：DeepSeek V4 Pro 按 plan 任务块实现，每块测试绿再进下一块

---

## 〇、目标与范围

把 Argus 的数据治理能力（`backend/argus/governance/`，801 行，双引擎质量规则）平移成 TARS 的一个**新增 module**，接 TARS 的 datasource 脊柱，配一个 Vue3 治理页。

**本设计覆盖**：阶段0（地基）+ 阶段1（治理后端平移 + Vue3 治理页）。

**明确不做（YAGNI，推到后续阶段）**：报表、鉴数联动、连接器对齐、文件类连接器（CSV/Excel/Mockup）、字段加密、标准库、血缘、AI 推断规则（infer_rules）。首期只做：**接 TARS 已支持的库 + 6 类质量规则 + 校验报告 + 一个 Vue3 治理页**。

**回退基线**：`v5.2.0-pre-fusion`（已打 tag 并推 Gitee）。融合改坏可 `git reset --hard v5.2.0-pre-fusion`。

---

## 一、模块落点与边界

**新 module 位置**：`backend/tars/governance/`（平移 Argus 801 行）。路由 `backend/tars/governance/api/router.py`，prefix `/api/governance`。

**接入 TARS 三处约定**（已核实）：

1. `config/modules.yaml` 加 `optional.governance.enabled` —— YAML 驱动，无需改 `modules/registry.py` 代码。
2. `main.py` 条件挂载：`if module_registry.is_enabled("governance"): app.include_router(governance_router)`（沿用 bi/insight 范式，`main.py:525-542`）。
3. 鉴权：`router.dependencies = [Depends(require_module("governance"))]`，Principal 自动注入（`api/_auth.py:280-335`）。

**四层结构**（沿用 Argus 解耦，只换数据源依赖）：

| 层 | 来源 | 改动 |
|---|---|---|
| `rules/builtin.py`（203 行，6 类纯函数规则） | Argus 原样搬 | **零改动** |
| `expectations/`（GE 封装 266 行） | Argus 原样搬 | GE 当库用，缺失优雅降级 |
| `engine.py`（122 行，双引擎路由） | Argus 搬 | 只把 `ResultSet` 来源换成新适配层 |
| `service.py`（119 行，CRUD + 编排） | Argus 搬 | `core.models.Connection/Dataset` → TARS `DataSourceStore` |
| `models.py`（QualityRule/CheckRun/RuleResult） | Argus 搬 | 表定义迁进 TARS 迁移框架 |

**边界硬约束**：治理只**读** `bi_store` 的 datasource，不改 insight/agent/bi 任何现有代码，新增表走 `database/migrations.py`。

---

## 二、取数适配层 `fetch_rows` 与数据流

**新增文件**：`backend/tars/governance/datasource_adapter.py`，只做一件事——把「datasource_id + 表/SQL」变成内存里的行集。

```python
def fetch_rows(datasource_id, *, table=None, sql=None, max_rows=10000) -> ResultSet:
    # 1. store = get_bi_store(); ds = store.get_by_id(datasource_id, tenant_id)
    #    tenant_id 取自 principal（v5 单组织 = org_default），行级归属另按 user_id
    # 2. config = ConnectionConfig.from_url(ds.connection_url)
    # 3. 复用 TARS 现有连接器执行 SELECT(下推 LIMIT max_rows+1)
    # 4. 返回 {"rows": [...], "column_names": [...], "truncated": bool}
    # 注：table 与 sql 二选一，互斥；table 模式生成 SELECT * FROM table
```

**关键设计点**：

- **truncated 诚实标注**：拉 `max_rows+1` 行，超了就截断并标 `truncated=True`，质量报告如实写「基于前 N 行抽样」。沿用 Argus 已验证的诚实做法，不假装全表校验。
- **只读**：只发 SELECT，适配层不接受写语句。
- **统一 ResultSet 形态**：`{rows, column_names, truncated}`，正好对上 Argus `engine.py` 现在吃的结构，所以规则执行逻辑一行不用改。

**数据流（跑一次质量校验）**：

```
POST /api/governance/rules/{id}/run
  → service.run_validation(rule_id, principal)
  → datasource_adapter.fetch_rows(ds_id, table=...)   ← 新适配层，接 bi_store
  → engine.run_checks(result_set, rules, ge_engine)    ← Argus 原逻辑，不改
  → 存 CheckRun + RuleResult(走 TARS 迁移框架的新表)
  → 返回 QualityReport(通过率/异常样本/truncated 标注)
```

**划界理由**：`fetch_rows` 是治理与 TARS 数据层之间唯一的接触点。将来 insight 执行引擎演进、或 bi_store 重构，只要 `fetch_rows` 签名不变，治理内部零感知。同一个 `datasource_id` 既能被 insight 问数、又能被治理校验——满足「同一 datasource_id 贯穿全平台」的防割裂硬指标。

---

## 三、数据模型与测试策略

**新增表**（Argus 原有，搬进 TARS 迁移框架）：

| 表 | 用途 | 关键列 |
|---|---|---|
| `quality_rules` | 规则定义 | id, datasource_id, table_name, kind(6 类), engine(builtin/ge), params_json, **user_id**, created_at |
| `check_runs` | 校验执行记录 | id, rule_id, status, total_rows, truncated, started_at, finished_at |
| `rule_results` | 单行/单规则结果 | id, check_run_id, passed, failed_count, sample_json |

**接入规范**（已核实）：

- 表定义写进 `database/migrations.py`（CREATE TABLE IF NOT EXISTS + guarded ALTER），迁移自动应用。
- @dataclass 模型放 `governance/models.py`，CRUD 走 `governance/repository.py`（沿用 TARS Repository 模式）。
- **多用户对齐**：每张表带 `user_id` 列，过滤 `user_id=?`，对齐 TARS v5 单组织多用户，不带 tenant 隔离。

**测试策略**（沿用 `backend/tests/` + conftest 夹具）：

- **纯函数测试**：`rules/builtin.py` 6 类规则喂构造数据断言——Argus 原测试整体搬，零依赖最稳。
- **适配层测试**：`fetch_rows` 用 conftest 的 `:memory:` SQLite + 临时表，验证 truncated 截断逻辑。
- **engine 测试**：builtin 双引擎路由 + GE 缺失降级（"GE engine not available"）。
- **API 集成测试**：用 conftest 的 `setup_main_api_auth` 建 datasource → 建规则 → 跑校验 → 断言 QualityReport。
- **GE 用例**：GE 装了才跑，没装 skip（沿用 Argus 隔离做法）。

**阶段验收硬指标**：`config/modules.yaml` 开 governance → 建一个连 SQLite 的 datasource → 配非空规则 → 跑校验 → 拿到含通过率和异常样本的 QualityReport。全链路通 = 阶段1 后端达标。

---

## 四、阶段0 地基、前端范围、错误处理

**阶段0 地基**（治理平移前的脊柱打通）：

1. **空 module 骨架**：`config/modules.yaml` 注册 governance + `main.py` 条件挂载 + `/api/governance/health` 能返回——验证新 module 接入 TARS 启动流程。
2. **datasource 脊柱验证**：`fetch_rows` 先单独跑通——给一个 bi_store 里的 datasource_id，能拉回 `{rows, columns, truncated}`。这是阶段1 的前置依赖。
3. **连接器对齐**（战略 spec 点名的工程量，但**按需做**）：Argus 文件类连接器（CSV/Excel/Mockup，130 行）+ 字段加密 —— **阶段0 先不做**，治理首期接 SQLite/PG 等 TARS 已支持的库即可验收。文件连接器留到真有 Excel 数据源需求时再补。

**Vue3 治理页范围**（阶段1 前端，YAGNI 收窄）：

- 一个 `/governance` 页，质量规则单 Tab（标准库/血缘留后续）。
- 规则列表 + 新建规则表单（6 类规则动态参数）+ 跑校验按钮 + QualityReport 展示（通过率 + 异常样本 + truncated 提示）。
- 复用 TARS 现有 Vue3 组件 / 请求封装，**不引入新 UI 框架**。
- AI 推断规则（infer_rules）降级入口 —— **阶段1 先不接**，留到鉴数联动阶段。

**错误处理**（沿用 TARS 现有约定）：

- datasource 不存在 / 连不上 → 走 TARS 统一错误响应信封（v5.0.5 已有），前端提示「数据源不可用」。
- GE 未安装 → engine 优雅降级，builtin 规则照跑，GE 类规则返回「引擎不可用」而非崩溃。
- 拉数超 max_rows → 不报错，truncated=True + 报告标注抽样。

**本阶段砍掉的（YAGNI）**：报表、鉴数联动、连接器对齐、文件类连接器、字段加密、标准库、血缘、AI 推断规则。首期只做「接已有库 + 6 类规则 + 校验报告 + 一个 Vue3 页」。

---

## 五、协作约定

延续既有方式：用户做规划+设计+评审，DeepSeek V4 Pro 按 plan 任务块实现，每块测试绿再进下一块。本 spec 之后转入 writing-plans 拆任务块。
