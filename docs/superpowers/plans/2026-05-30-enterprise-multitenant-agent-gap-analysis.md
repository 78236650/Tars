---
doc_type: analysis
status: superseded-direction
platform_version: v4.4.0
date: 2026-05-30
author: 架构分析（Claude）
supersedes_note: 方向已于 2026-05-30 调整 —— 用户确认不做 SaaS 多租户，改做"单组织多用户协作 + 并发"。实施主线见 2026-05-30-tars-v5.0.0-multiuser-design.md。本文档保留为完整的能力盘点背景参考；其中"多租户隔离(G1/G2)"部分已不适用，但其余能力盘点、垂直缺口(V1/V2)、工程化缺口(E1-E9)仍然准确有效。
---

# TARS 能力差距分析（背景参考 · 多租户方向已调整）

> **⚠️ 方向变更说明**：本文档原按"企业级 SaaS 多租户"方向分析。用户已明确：**不做多租户，改做单组织内多用户协作 + 并发**。第二部分的 G1/G2（租户隔离）已被新主线取代，请以 `2026-05-30-tars-v5.0.0-multiuser-design.md` 为执行依据。本文档其余部分（现状盘点、垂直缺口、工程化缺口）仍准确，作为背景保留。
>
> **结论先行**：TARS 已是一个功能完整、架构清晰的 AI Agent 原型，记忆系统、知识库、工具/技能/模型可插拔、子 Agent 编排都达到了相当成熟度。原分析识别出的缺口中，**真正阻断"多用户协作平台"定位的是：`tenant_id == user.id` 导致语义混乱、SQLite 单写并发瓶颈、对外仅单 API Key 认证**。垂直 Agent 仍是 prompt 壳（V1）、workflow 仍硬编码（G3）则属于后续版本。

---

## 第一部分：现状能力盘点（已核实）

下表是对当前代码的真实评估（已逐条核对文件:行号），分"已具备 / 半成品 / 缺失"。

### 1.1 已经做得不错的能力（地基扎实）

| 能力域 | 现状 | 证据 |
|---|---|---|
| **记忆系统** | Core(4区块) + Archival(episodic/semantic) + Working Context 场景画像；四路融合召回（实体40%/时间20%/向量30%/关键词10%）+ Ebbinghaus 衰减；三层去重 | `memory/manager.py`、`memory/router.py:24`、`memory/decay.py`、`analysis/scene_analyzer.py` |
| **垂直实体建模** | `entities.type` 自由字符串，已定义 8 类港航实体（terminal/berth/crane/vessel/voyage/yard/cargo_owner/container）+ 6 类关系 | `memory/domain_schema.py:13` |
| **知识库 RAG** | 7 种文档解析 + LLM enrichment（QA/摘要/指标）+ 向量检索 + CrossEncoder rerank + 上下文拼接 | `knowledge/`、`reranker/cross_encoder.py` |
| **多 Agent 编排（基础）** | 主 Agent + 8 个子 Agent（含 berth/yard/vessel 港航）；顺序/并行/条件分支；编排记忆三表落库（agent_tasks/agent_task_outputs/agent_collaboration_ctx 共享黑板） | `agent/subagent_manager.py`、`orchestration/multi_agent_orchestrator.py`、`orchestration/orchestration_memory.py` |
| **工具/技能/模型可插拔** | 工具注册表 + 插件热加载 + 路径沙箱；MCP server；技能租户隔离路径；Provider 注册表 + Fallback 链 | `tools/registry.py`、`tools/plugin_loader.py`、`mcp/tars_memory_server.py`、`models/registry.py` |
| **RBAC + 审计** | 8 个预置角色，工具级/模块级/工作空间级权限；审计日志带 tenant 维度，覆盖工具/权限/登录/配置/技能 | `gateway/role_template.py:31`、`security/audit.py` |
| **可靠性（编排）** | Act Policy 重试、plan_resume 断点续跑、plan_gate 审批门控、handoff 人工审批 | `orchestration/executor.py:84`、`orchestration/plan_resume.py`、`orchestration/plan_gate.py` |
| **前端** | Vue3 + Vite + TS + Tailwind，83 个组件；含 orchestration 可视化、memory/knowledge/admin/bi 面板 | `frontend/src/components/orchestration/` |
| **测试** | 175 个测试文件，覆盖 API/记忆/技能/工具/编排/知识库 | `backend/tests/` |

### 1.2 半成品 / 被关闭的能力

| 能力 | 状态 | 证据 |
|---|---|---|
| 记忆压缩/知识晋升/记忆树/turn发布 | 4 个 env 开关默认 **False**（垂直场景刻意降级，可一行打开） | `config/memory.py:31-34` |
| DAG 编排 | planner 支持 `depends_on` 字段，但 executor **未实现拓扑排序**，实际只跑两阶段（并行→串行） | `orchestration/planner.py`、`subagent_manager.py:250` |
| 多通道接入 | channels 框架存在，但**只实现了 WebSocket**，无微信/钉钉/Slack 适配 | `channels/websocket.py` |
| 对外认证 | 有 password_hash(PBKDF2) + user_sessions 表，**但 gateway/auth 对外只认单个 env API Key**，无 JWT 签发/校验 | `gateway/auth.py:26`、`database/user_store.py:109` |

---

## 第二部分：致命缺口（阻断企业级多租户定位）

这三条是**产品定位级**的缺口——不补，"企业级多租户"和"行业 workflow 平台"在语义上不成立。

### 缺口 G1（致命）：没有"组织/租户"实体层级，`tenant_id == user.id`

**问题**：当前 `main.py:649,662` 直接 `tenant_id = user.id`，`users` 表无 `org_id`/`tenant_id` 列，全局 grep 无任何 organization 概念。这意味着：

- 租户 = 单个用户。**同一家港航企业的调度员、船务、堆场主管无法共享同一租户的记忆、知识库、实体图谱。**
- A 员工录入的"QC-7 故障"，B 员工的 Agent 看不到——垂直领域最值钱的"组织级共享知识"无法沉淀。
- 计费、配额、数据归属都无法以"企业"为单位。

**目标模型**（企业级多租户标准三层）：

```
Tenant(组织/企业)  ──1:N──>  User(成员)  ──N:M──>  Team/Role
      │                          │
      └── 租户级资源：记忆 / 知识库 / 实体图谱 / 技能 / 模型配置 / 配额
                                 └── 用户级私有：private-scope 记忆 / 会话
```

**升级方案**：
1. 新增 `tenants` 表（`id/name/plan/quota_json/model_config_json/created_at/status`）。
2. `users` 表加 `tenant_id` 外键（迁移：存量用户各自建一个同名 tenant，`tenant_id = "t_" + user.id`，保持数据不丢）。
3. **解耦 tenant_id 与 user_id**：记忆/知识库的 `scope='shared'` 数据按 `tenant_id` 共享，`scope='private'` 按 `user_id` 隔离。`MemoryManager.for_tenant()` 已是租户入口，只需让 tenant_id 真正来自组织而非用户。
4. 记忆/实体的查询过滤改为 `WHERE tenant_id=? AND (scope='shared' OR user_id=?)`。

**工作量**：中（表结构 + 迁移 + 查询过滤改造，约 3-4 人天）。**优先级：P0**。

### 缺口 G2（致命）：tenant_id 靠手动透传，无全局上下文，跨租户泄漏风险

**问题**：无 `contextvars`/中间件自动注入租户上下文。`x_tenant_id` 是每个 endpoint 手动从 Header 取（`main.py:681,731,783...`），任何一处遗漏过滤就跨租户泄漏。`backend/` 中 tenant_id 出现上千处，全靠人工保证一致性——这是数据安全定时炸弹。

**升级方案**：
1. 新增 `TenantMiddleware`：从 JWT/Session 解析 tenant_id + user_id，写入 `contextvars.ContextVar`。
2. 数据库 repository 层统一从 contextvar 读租户，**强制注入 WHERE 过滤**，应用代码无法绕过（参考 row-level security 思路在应用层实现）。
3. 提供 `get_current_tenant()` / `get_current_user()` 全局函数，删除所有手动透传。
4. 增加跨租户访问的审计告警 + 测试用例（造两个租户互访必须 403）。

**工作量**：中（中间件 + repository 改造 + 测试，约 3 人天）。**优先级：P0**。

### 缺口 G3（致命）：行业 workflow 硬编码，无声明式/可视化编排，新流程必须改代码

**问题**：港航 workflow 在 `multi_agent_orchestrator.py:13-37` 用 `if 关键词 then subtask` **硬编码**。`decompose_goal()` 是规则函数，新增一条业务流程（如"危险品船舶进港审批流"）必须改 Python 代码、重新部署。这与"垂直领域多 Agent 协调**行业 workflow** 平台"的定位直接冲突——行业 workflow 的核心价值就是**可配置、可沉淀、可复用**。

**目标**：workflow 成为**一等公民数据**，声明式定义 + DAG 执行 + 可视化编排。

**升级方案**：

1. **Workflow 定义模型**（声明式，存库）。新增 `workflows` 表，定义如下结构（YAML/JSON）：
```yaml
workflow: vessel_inbound_approval        # 船舶进港审批
tenant_id: t_yuanhong
trigger: { type: manual | event | cron }
nodes:
  - id: berth_check
    agent: berth                          # 复用现有子 Agent
    inputs: { vessel: "${input.vessel}" }
  - id: yard_plan
    agent: yard
    depends_on: [berth_check]             # ← DAG 依赖
    inputs: { berth: "${berth_check.output.berth_id}" }
  - id: hazmat_gate
    type: approval                        # 复用 plan_gate 人工审批
    when: "${input.is_hazmat == true}"    # ← 条件分支
    depends_on: [yard_plan]
  - id: dispatch
    agent: vessel
    depends_on: [hazmat_gate]
edges_on_failure: { berth_check: compensate_release_berth }  # ← 失败补偿
```

2. **DAG 执行引擎**：把 `executor.py` 升级为真正的拓扑排序调度器（现已有 `depends_on` 字段，只差拓扑排序 + 节点状态机）。支持 节点级 重试/超时/补偿。

3. **Workflow 可视化编辑器**（前端）：已有 `2026-05-30-workflow-editor-design.md`，对接此声明式模型。节点拖拽 = 上述 nodes，连线 = depends_on。

4. **Workflow 即资源**：按 tenant 隔离，可版本化、可复制为模板、可审批上线。这是平台从"工具"变"行业平台"的关键。

**工作量**：大（定义模型 + DAG 引擎 + 编辑器对接，约 8-10 人天）。**优先级：P0（这是定位的核心）**。

---

## 第三部分：垂直领域能力缺口（港航 Agent 还是"prompt 壳"）

这一部分决定 TARS 是"会聊港航的通用 Agent"还是"真能干港航活的垂直 Agent"。

### 缺口 V1（高）：港航子 Agent 无真业务工具，靠 LLM 编造数据

**问题**：`berth/yard/vessel` 子 Agent 仅 3-19 行，`execute()` → `run_port_agent()` → 纯 LLM chat（`subagents/port/_helpers.py`）。系统提示词里写了泊位约束（水深/船长/潮汐），但**没有任何数据源接入**——LLM 会"编"一个泊位分配方案，无法验证、不可信、不可执行。注意：`wind_stowage`（风电配载求解器）是个例外，它接了真实算法，证明这条路走得通。

**升级方案**（把港航 Agent 从壳变成真业务）：
1. **领域工具层**：为每个港航 Agent 配真工具——
   - `berth`: 泊位主数据查询 + 泊位占用时间轴 + 靠泊约束校验（水深/船长/潮汐窗口）+ 冲突检测。
   - `yard`: 堆场库存查询 + 箱区分配 + 翻箱率估算。
   - `vessel`: 船舶 ETA/AIS 接口 + 航次计划 + 配载（已有 `vessel_plan` 模块和 `wind_stowage` 求解器可复用范式）。
2. **约束求解器**：泊位/堆场分配是经典 CSP/LP 问题，参考 `wind_stowage_solve` 的做法接 OR-Tools / 启发式求解，而非让 LLM 拍脑袋。
3. **数据校验闸**：Agent 产出的方案必须经工具校验（如"这个泊位水深够不够"），校验失败回退重规划。
4. **数据源适配器**：对接企业现有 TOS（码头操作系统）/ 船代系统的只读 API 或数据库视图。

**工作量**：大（每个 Agent 一套工具 + 求解器，约 10-15 人天，可分 Agent 增量）。**优先级：P1**。

### 缺口 V2（中）：编排无补偿事务、无 DAG 拓扑、无中间人工介入

**问题**：多 Agent 协调失败无回滚（berth 分配成功但 yard 失败，berth 不会释放）；只支持最终审批，流程中间无法暂停让人改。

**升级方案**：随 G3 的 DAG 引擎一起做——节点级 `on_failure` 补偿动作、节点级 approval 网关（复用 `plan_gate`/`approval_requests` 表）、拓扑排序替代两阶段执行。**优先级：P1（并入 G3）**。

---

## 第四部分：企业级工程化缺口

这部分与 `2026-05-30-tars-hardening-roadmap.md` 有重叠（CI/上帝文件拆分/DB repository 解耦已在该 roadmap 覆盖），此处只列**未被覆盖**或需强调的。

| 编号 | 缺口 | 严重度 | 说明 / 方案 | 与现有 roadmap 关系 |
|---|---|---|---|---|
| E1 | **SQLite 单写入瓶颈** | 高 | `connection.py:23 dialect="sqlite"` 硬编码，单写锁无法支撑多租户并发写。需 Postgres。 | roadmap 只解耦到 repository 层"留接口不迁移"；**企业级多租户必须真迁 Postgres**，建议 v5.0 落地 |
| E2 | **JWT/Session 认证 + SSO** | 高 | 对外只认单 env API Key。需 JWT 签发/校验（含 tenant_id claim）+ 刷新令牌；企业必备 SSO/SAML/OIDC 对接企业 IdP。 | roadmap 未覆盖 |
| E3 | **租户级配额 / 计费 / 用量** | 高 | `provider_usage` 表已记 token（带 tenant_id），但**无配额检查、无计费、限流是全局/用户级非租户级**。需 per-tenant QPS + token 配额 + 用量账单。 | roadmap 未覆盖 |
| E4 | **可观测性** | 中 | 无 `/health`、无 Prometheus 指标、无 OpenTelemetry 链路追踪，仅 print 日志。企业运维必备。 | roadmap P2 有 dashboard，但缺 metrics/tracing/health |
| E5 | **分布式任务队列** | 中 | `scheduler.py` 进程内 cron，单点。多实例部署需 Celery/RQ/arq + Redis。 | roadmap 未覆盖 |
| E6 | **水平扩展 / 部署** | 中 | 单体 docker-compose（`--workers 1`），无 K8s manifest。配合 E1/E5 才能多副本。 | roadmap 未覆盖 |
| E7 | **CI/CD** | 中 | 有 pre-commit，roadmap 已规划 Gitee Go。确保多租户/隔离测试进 CI 门禁。 | roadmap P0 已覆盖 |
| E8 | **租户级模型配置** | 中 | 无法为不同租户配不同 LLM/参数/密钥。G1 的 `tenants.model_config_json` 落地后补此逻辑。 | roadmap 未覆盖 |
| E9 | **静态数据加密 / 密钥管理** | 中 | API Key/敏感属性明文或仅 hash 存 SQLite。需字段级加密 + KMS/Vault。 | roadmap 未覆盖 |

---

## 第五部分：升级路线图（v5.0.0）

按"先让多租户在语义上成立 → 再让 workflow 可配置 → 再让垂直 Agent 真能干活 → 最后工程化扛量"的顺序分四个里程碑。

### M1：多租户地基（P0，~8 人天）
- G1 组织/租户实体层（`tenants` 表 + `users.tenant_id` + 迁移 + scope 共享逻辑）
- G2 TenantMiddleware + contextvars + repository 强制过滤 + 跨租户隔离测试
- E2 JWT 认证（tenant_id claim）
- **验收**：两个租户、每租户多用户；A 租户用户绝对看不到 B 租户数据（测试断言 403）；同租户内 shared 记忆/知识库互通，private 隔离。

### M2：声明式 Workflow 平台（P0，~10 人天）
- G3 Workflow 定义模型（`workflows` 表 + YAML/JSON schema）
- G3+V2 DAG 执行引擎（拓扑排序 + 节点重试/超时/补偿/审批网关）
- 对接 `2026-05-30-workflow-editor-design.md` 可视化编辑器
- **验收**：不改代码，纯配置定义一条"船舶进港审批流"并跑通，含一个条件分支 + 一个人工审批节点 + 一次失败补偿。

### M3：港航垂直 Agent 实化（P1，~15 人天，可增量）
- V1 berth/yard/vessel 领域工具 + 约束求解器（复用 wind_stowage/vessel_plan 范式）
- 数据源适配器（对接 TOS/船代只读接口）
- 数据校验闸
- **验收**：给定真实船舶/泊位数据，Agent 产出的泊位分配方案通过约束校验、可执行、可解释，而非 LLM 编造。

### M4：企业级工程化（P1/P2，~15 人天）
- E1 Postgres 迁移（基于 roadmap 已解耦的 repository 层 + sql_dialect）
- E3 租户级配额/计费/用量
- E4 可观测性（/health + Prometheus + OTel）
- E5/E6 任务队列 + K8s 多副本
- E8/E9 租户级模型配置 + 字段加密
- **验收**：多副本部署、并发多租户压测无数据串扰、有监控面板和用量账单。

---

## 第六部分：一句话总结

| 维度 | 现在是 | 升级后应是 |
|---|---|---|
| 多租户 | 用户即租户（伪多租户） | 组织→用户→资源 三层真多租户 |
| Workflow | 硬编码规则函数 | 声明式数据 + DAG + 可视化编排 |
| 港航 Agent | 会聊港航的 LLM 壳 | 接数据源+求解器的真业务 Agent |
| 数据库 | SQLite 单写 | Postgres 并发 |
| 认证 | 单 env API Key | JWT + SSO/SAML |
| 可观测 | print 日志 | health + metrics + tracing |

**最小可信的"企业级垂直多 Agent 平台" = M1（真多租户）+ M2（可配置 workflow）+ M3 至少一个 Agent 实化。** 这三步做完，定位才成立；M4 决定能扛多大规模。


