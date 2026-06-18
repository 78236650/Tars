# Argus × TARS 融合战略

> 日期：2026-06-18
> 状态：已确认方向，待落地
> 决策性质：**战略转向** —— 从「Argus 当平台、调用 TARS 当大脑」改为「Argus 能力融入 TARS、TARS 成为统一平台」

---

## 一、产品定位

**一个 AI 原生的统一数据平台**：在 TARS 这根成熟脊柱上，长出四个共享同一数据底座的模块——

> **鉴数（dataagent）= TARS insight** · **数据报表** · **数据治理** · **孪生 workflow（将来）**

不是「Argus 调 TARS」，而是「Argus 的能力成为 TARS 的模块」。
- TARS 提供：多租户、认证、连接/数据源、Agent 编排、向量记忆、生产级 NL2SQL 引擎。
- Argus 贡献其独有能力：数据治理（双引擎质量）+ 数据报表（中立图表模型）。

目标是「生产可用」，不是玩具。

---

## 二、为什么是「融入 TARS」（实测依据）

| 维度 | TARS | Argus |
|---|---|---|
| 后端 | 54266 行、169 测试 | 6700 行、127 测试 |
| 前端 | Vue3 + Vite，28773 行 | React + AntD，3400 行 |
| 多租户/认证 | ✅ tenant + security | ❌ 单 API Key |
| Agent/编排 | ✅ agent + orchestration + mcp + skills | ❌ |
| 向量库/记忆 | ✅ vectorstore + memory | ❌ |
| NL2SQL/BI 引擎 | ✅ insight 7480 行（生产级） | ❌ 614 行玩具 |
| 数据治理 | ❌ 没有 | ✅ 双引擎（builtin+GE） |
| 报表/看板 | ❌ 没有（bi 仅荐图） | ✅ chartspec/aggregate |

三条结论：
1. TARS 才是够格的平台脊柱（多租户/认证/Agent/向量/NL2SQL 全有，Argus 要从零补）。
2. Argus 的治理 + 报表恰好填 TARS 的空白，是净增量、不打架。
3. dataagent 不用重写——它就是 TARS insight。

---

## 三、统一脊柱（防割裂的根基）

所有模块共享 TARS 的这几样，绝不各搞一套：

| 共享层 | 用谁的 | 说明 |
|---|---|---|
| 连接/数据源 | **TARS ConnectionConfig** | 已支持 8 种库（mysql/postgresql/oracle/sqlserver/clickhouse/sqlite/doris/jdbc），是 Argus 6 连接器的超集。补入 Argus 的 CSV/Excel/Mockup + 字段加密 |
| 数据集/语义 | 统一 Dataset 抽象 | 复用 TARS insight 的 datasource + 字段语义（role 分类已有） |
| 认证/租户 | **TARS tenant + security** | Argus 单 API Key 作废，统一走 Principal |
| Agent 能力 | **TARS insight/agent** | 报表荐图、治理推规则、问数都走它 |

**「不割裂」的验收硬指标**：一个数据集建好后，能在报表里画图、在治理里配规则、在 dataagent 里问数、被血缘追踪——同一个 datasource_id 贯穿全平台。

**连接模型对齐方向**：以 TARS ConnectionConfig 为标准，把 Argus 独有的（文件类连接器 + 字段加密 + Oracle thin 细节）补进去。Argus 不反向输出连接模型。

---

## 四、模块策略

**① 鉴数 dataagent = TARS insight（已生产级，做打磨）**
不重写。insight 的 `/ask`、`/forge`、`/profile`、关系推断、指标沉淀已就绪。工作 = 作为平台「鉴数」模块对外 + 补前端体验。

**② 数据治理 = 平移 Argus governance 进 TARS（净增量）**
后端把 `governance/`（builtin 6 类 + GE 封装 + engine 双引擎路由）迁成 TARS 新 module（`/api/governance`），数据源改读 TARS datasource。GE 当库用。后端逻辑基本不动。

**③ 数据报表 = 平移 Argus report + Vue3 重写前端**
路线已定：**自研中立模型 + ECharts**，不嵌 Superset。后端 `chartspec/aggregate/renderer` 平移进 TARS（`/api/report`）；`chartspec→ECharts option` 纯函数搬过来，前端用 **Vue3 + ECharts** 重画（React 那套丢弃）。荐图走 insight。

**④ 孪生 workflow** —— 用户想好了再加。长在 TARS 已有的 orchestration/pipelines 上，不再自建 Worker。

---

## 五、迁移阶段（每阶段独立可验收）

- **阶段 0（地基）** ✅起点：在 TARS 里建治理/报表两个空 module（`modules/registry.py` 注册 + `APIRouter(prefix=...)` 路由骨架），打通 datasource 脊柱——确认新 module 能读到 TARS datasource。连接器对齐（补 Argus 文件类连接器 + 加密）是本阶段主要工程量。
- **阶段 1（治理先行）** ✅起点：平移治理后端 → 接 TARS datasource → Vue3 治理页。选治理打头阵，因为纯后端平移、风险最低、TARS 完全没有、价值最直观。
- **阶段 2（报表）**：平移报表后端 → Vue3 + ECharts 报表页 → 接 insight 荐图。
- **阶段 3（鉴数打磨 + 四模块联动）**：insight 作为鉴数模块对外，打通「数据集→图表→规则→问数→血缘」串联。

**已确认起点 = 阶段 0 + 阶段 1（治理先行）。**

---

## 六、风险与约束

1. **在 54k 行成熟代码里动刀** > 空地盖楼。严守模块边界：治理/报表作为**新增 module**，尽量只读 TARS datasource/tenant，不改 insight/agent 核心，避免碰坏 TARS 现有功能。
2. **TARS 需有版本控制纪律**：融入意味着在生产级仓库改，改坏要能回滚。（Argus 的 git 已丢失，勿把此习惯带进 TARS。）
3. **连接器对齐工程量**：Argus 的字段加密、Oracle thin、文件类连接器并进 TARS ConnectionConfig，是阶段 0 主要活。
4. **DeepSeek 上手成本**：先读懂 TARS 的 module/registry/tenant 约定才能动手。建议第一个任务块 = 「摸清 TARS 模块接入规范」。

---

## 七、协作约定

延续既有方式：用户做规划+设计+评审，DeepSeek V4 Pro 按 plan 任务块实现，每块测试绿再进下一块。模块级 spec/plan 后续落在 **TARS 仓库**（本战略文档作为决策记录留在 Argus docs，承接既有 10 份 spec 的历史）。
