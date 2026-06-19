# TARS Changelog

## v6.0.1 (2026-06-19) — v6 时代：两层架构 + 港航数据平台

### 架构

- **Layer1 Agent Core** — 对话、记忆、工具、Skills、Wiki、会议、Gateway（保留并收敛）
- **Layer2 Port Data Platform** — BI、鉴数(Insight)、数据治理、数据报表、语义层
- **`bootstrap/layer1.py` + `layer2.py`** — 可选模块分层初始化；`core/ports.py` Port 契约
- **`data/spine.py`** — DataSpine 统一只读取数，governance/report 解耦

### 新功能

- **数据治理** — `governance/` 六类质量规则 + check runs（Argus 融入）
- **数据报表** — `report/` ChartSpec 聚合 + Vue3 ECharts 渲染
- **语义层** — `semantic/` 港航术语库 seed（30+ 术语）、字段绑定、问数 glossary 增强
- **前端导航分组** — Agent 核心 / 数据平台；新增 `/semantic` 术语库页

### 收敛

- 默认冻结 `presales`、`vessel_plan`、`wind_stowage`
- Evolution `feedback_only` 模式，关闭 case distillation 自进化路径
- `modules.yaml` / `registry.py` 对齐两层模块；`knowledge` phantom core 移除

### 数据库迁移

- v7: `glossary_terms` / `field_semantics`
- v8: insight INS-2 表（从 `connection.py` 迁至 central migrator）

### 设计文档

- [docs/superpowers/specs/2026-06-19-tars-two-layer-architecture-design.md](docs/superpowers/specs/2026-06-19-tars-two-layer-architecture-design.md)

---

## v5.2.0 (2026-06-16) — 记忆管理 + MCP 客户端 + 工具发现 + 置信度声明

### 新功能

- **`MemorySleepAgent` 休眠期记忆管理** — `consolidate_duplicates`（向量+Jaccard去重合并）、`resolve_conflicts`（Jaccard+LCP BFS冲突分组降级）、`decay_stale_memories`（衰减+清理）三个方法已实现。`MemoryManageExecutor` 通过 Cron 定时调度。
- **MCP 客户端模块** — `tars/mcp/`：JSON-RPC 2.0 通信层（Stdio + SSE）、`MCPToolAdapter(BaseTool)` 工具适配器、`MCPRegistry` 服务器生命周期管理。可连接外部 MCP 服务器并动态注册工具到 `ToolRegistry`。
- **分层工具发现** — `ToolRanker`（CrossEncoder + FTS 降级），`agent._get_allowed_tool_schemas(user_query, top_k)` 支持按查询相关性动态 Top-K 注入（默认全量注入，`top_k=0`）。
- **置信度声明规则** — `prompt_builder.py` 注入 LLM 不确定性声明引导：推测标注、过时数据提醒、专业免责、未验证代码提示。
- **Run 生命周期** — `runs` 表记录每次 Agent 执行的完整状态（`queued → running → completed/failed`），WebSocket 新增 `run_started` / `run_completed` / `run_failed` 事件。
- **`provider_usage` 添加 `user_id` 列** — Token 用量可按用户维度统计，新增 `/api/user/usage` 端点。
- **Run REST API** — `GET /api/sessions/{id}/runs`、`GET /api/runs/{id}`。

### 修复

- **新 session WebSocket 路由断裂** — Agent 创建新 session 后 UUID 变更，导致事件路由失败（用户只看到 `thinking_start` 然后静默）。修复：Agent 在创建新 session 后调用 `channel.manager.bind_session(new_id)`。
- **加密密钥分离** — `.env` 新增 `TARS_ENCRYPTION_KEY`，与 `TARS_JWT_SECRET` 分离，解决旧加密数据与新 JWT 密钥不兼容的密文损坏问题。

### 文件清单

| 类型 | 文件 |
|------|------|
| 新增 | `backend/tars/mcp/__init__.py`, `client.py`, `tool_adapter.py`, `registry.py` |
| 新增 | `backend/tars/tools/tool_ranker.py` |
| 新增 | `backend/tars/tools/validators.py` |
| 新增 | `backend/tars/cron/executors/memory_manage.py` |
| 新增 | `backend/tars/memory/sleep_agent.py` |
| 修改 | `backend/tars/memory/sleep_agent.py`（空壳 → 真实实现） |
| 修改 | `backend/tars/cron/executors/memory_manage.py`（传入 db） |
| 修改 | `backend/tars/agent/agent.py`（分层工具发现 + session绑定修复） |
| 修改 | `backend/tars/agent/prompt_builder.py`（置信度声明规则） |
| 修改 | `backend/tars/main.py`（Run API + user usage + Reranker 加载） |
| 修改 | `backend/tars/channels/websocket.py`（Run 生命周期事件） |
| 修改 | `backend/tars/database/models.py`（Run dataclass） |
| 修改 | `backend/tars/database/connection.py`, `connection_pg.py`（runs 表 + user_id 列） |
| 修改 | `backend/tars/database/repositories/memory_repo.py`（provider_usage.user_id） |
| 修改 | `backend/tars/database/repositories/session_repo.py`（Run CRUD） |
| 修改 | `backend/tars/database/base.py`（Run 委托 + provider_usage 门面） |
| 修改 | `backend/tars/tools/dispatcher.py`（user_id 透传） |
| 修改 | `backend/tars/models/fallback.py`（user_id 透传） |
| 修改 | `frontend/src/stores/wsStore.ts`（run 事件 isGenerating toggle） |
| 修改 | `frontend/src/stores/chatRealtime.ts`（run 事件处理） |

---

## v5.0.5 (2026-05-xx)

- 聊天模型选择持久化 + crypto 解密失败不再泄漏密文
- 批次三 A5/A6 + 编排/记忆/安全硬化
- API key 加密存储 + 统一错误响应信封
- schema 迁移框架 + 数据库备份 + 优雅关闭
- 结构化日志 + 全链路 trace_id + Prometheus metrics
- 批次一安全硬阻塞修复

## v5.0.4

- 删除知识库模块 + Wiki 强化 + 多处修复
- 会议原音频下载按钮

## v5.0.3

- 工具执行结果验证层 (`ToolResultValidator`)
- MemorySleepAgent 骨架 + MemoryManageExecutor 注册
- ChromaDB 向量语义搜索
- 嵌入模型回退 + 异构向量兼容

## v5.0.0

- 多用户协作（org_default 组织池）
- JWT 登录 + API Key 双认证
- PostgreSQL 支持
- 单 worker 部署
