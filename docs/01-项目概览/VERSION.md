# TARS 版本对照（SSOT）

> **单一真相源**：对外说明「当前是什么版本」以本文件为准；`changelog` / `release-notes` / 根 `README` 均引用此处。

## 当前（稳定版）

| 项 | 值 |
|----|-----|
| **平台版本** | **v6.0.1** 「两层架构 — Agent Core + 港航数据平台」 |
| **OpenAPI** | `backend/tars/main.py` → `6.0.1` |
| **InsightForge 能力** | **INS-2.1.0**（`GET /api/insight/version`） |
| **上一平台 major** | v5.2.0（记忆管理 + MCP + 工具发现） |
| **推荐 Git tag** | `v6.0.1` |
| **生产数据库** | **PostgreSQL**（`DATABASE_URL`）；开发可继续 SQLite |

## v6.0.1 要点（2026-06-19）

| 维度 | 内容 |
|------|------|
| 架构 | Layer1 Agent Core + Layer2 Port Data Platform |
| 数据脊柱 | `data/spine.py` — 统一 `fetch_rows`，同一 `datasource_id` 贯穿问数/治理/报表/术语 |
| 语义层 | `semantic/` 港航术语库 + 字段绑定 + MetricQa glossary 增强 |
| 治理/报表 | governance + report 模块；ChartSpec + ECharts 前端 |
| 收敛 | 冻结 presales/vessel_plan/wind_stowage；Evolution feedback_only |
| Bootstrap | `bootstrap/layer1.py` + `layer2.py` 模块分层初始化 |

设计文档：[2026-06-19-tars-two-layer-architecture-design.md](../superpowers/specs/2026-06-19-tars-two-layer-architecture-design.md)

## v5.2.0 要点（2026-06-16）

| 维度 | 内容 |
|------|------|
| 记忆管理 | `MemorySleepAgent` 异步去重/冲突解决/衰减，Cron 定时调度 |
| MCP 客户端 | JSON-RPC 2.0 + Stdio/SSE，`MCPToolAdapter` 适配外部工具 |
| 工具发现 | `ToolRanker` 按查询相关性 Top-K 工具注入 |
| 置信度 | System Prompt 注入不确定性声明规则 |
| Run 生命周期 | `runs` 表 + WebSocket `run_started`/`run_completed`/`run_failed` 事件 |
| 用户用量 | `provider_usage.user_id` + `/api/user/usage` 端点 |
| Session 修复 | 新 session WebSocket 路由断裂修复 |

发布说明：[v5.2.0 实施计划](../../.trae/documents/tars_v5.2.0_implementation_plan.md)
变更日志：[CHANGELOG.md](../../CHANGELOG.md)

## v5.0.0 要点（2026-05-30）

| 维度 | 内容 |
|------|------|
| 定位 | 单组织多用户（**非** SaaS 多租户） |
| 身份 | JWT + API Key（集成） |
| 数据 | 组织池 `org_default`；private 按 `user_id` |
| 并发 | Postgres + `uvicorn --workers 1` |

发布说明：[v5.0.0-release-notes.md](./v5.0.0-release-notes.md)

## 历史版本（仍可用能力）

| 版本 | 主题 |
|------|------|
| **v5.0.5** | 安全加固 + 企业级就绪 |
| **v4.5.0** | 进出港计划 + Agent/OR 协同 |
| **v4.4.0** | 港航垂直 + 作业调度 MVP |
| **v4.3.4** | Superpowers + Wiki + 加固 |
| **v4.3.0** | Channels & Execution |

完整条目见 [changelog.md](./changelog.md)。

## Git 分支说明

| 名称 | 含义 |
|------|------|
| **产品版本** | v6.0.1（本文件、OpenAPI、发布说明） |
| **开发分支** | 以仓库当前分支为准；发版打 tag `v6.0.1` |

勿用 Git 分支名推断功能归属；以 changelog 与对应 release-notes 为准。

## 双轨版本（平台 vs 鉴数）

| TARS 平台 | InsightForge | 说明 |
|-----------|--------------|------|
| **v6.0.1** | INS-2.1.0 | 当前（两层架构 + 数据平台） |
| v5.2.0 | INS-2.1.0 | 记忆管理 + MCP + 工具发现 |
| v5.0.3 | INS-2.1.0 | 多用户隔离 + 安全加固 |
| v5.0.1 | INS-2.1.0 | 售前管理模块 |
| v5.0.0 | INS-2.1.0 | 多用户协作 + 并发底座 |
| v4.4.0 | INS-2.1.0 | 港航编排 MVP |
| v4.3.4 | INS-2.1.0 | 上一稳定 patch 线 |

能力 Git tag 建议：`insight-v2.1.0`（不替代平台 tag）。

## 文档入口

| 场景 | 文档 |
|------|------|
| 版本变更全文 | [changelog.md](./changelog.md) |
| **v5.2.0 实施** | [../../.trae/documents/tars_v5.2.0_implementation_plan.md](../../.trae/documents/tars_v5.2.0_implementation_plan.md) |
| **v5.0.0 发布** | [v5.0.0-release-notes.md](./v5.0.0-release-notes.md) |
| **从 v4.x 升级到 v5.0** | [UPGRADE_GUIDE_v5.0.0.md](../UPGRADE_GUIDE_v5.0.0.md) |
| v5.0 设计 | [multiuser-design.md](../superpowers/plans/2026-05-30-tars-v5.0.0-multiuser-design.md) |
| v4.4.0 发布 | [v4.4.0-release-notes.md](./v4.4.0-release-notes.md) |
| 作业调度使用 | [port-operations-user-guide.md](../04-运维文档/port-operations-user-guide.md) |
| 稳定版部署 | [deploy/README.md](../../deploy/README.md) |
| 部署详解 | [04-运维文档/deployment.md](../04-运维文档/deployment.md) |
| 设计稿索引 | [superpowers/README.md](../superpowers/README.md) |

---

*更新日期：2026-06-16*
