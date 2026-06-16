# TARS Changelog

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
