---
doc_type: plan
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# Core Brain Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 TARS 落地 Phase 2 的多租户核心能力，包括 `TenantContext`、按租户隔离的会话与记忆、以及复用 Agent 主逻辑的 `/api/invoke` REST 调用入口。

**Architecture:** 保持单个 `AgentV2` 实例不变，在请求入口层解析 `tenant_id`，通过 `TenantContext` 将租户态信息传入 Agent 与 Memory 层。数据库继续使用现有 SQLite 表，通过新增 `tenant_id` 字段和查询过滤实现隔离；WebSocket 与 REST 共用 `AgentV2.handle_message()` 主流程，差异只体现在入口适配器上。

**Tech Stack:** Python, FastAPI, SQLite, 现有 `AgentV2` / `MemoryManager` / WebSocket Channel 架构

---

## Summary

- 当前代码已经有单实例 `AgentV2`、全局 `MemoryManager`、`/ws` WebSocket 入口和多个 REST API，但没有任何租户级上下文对象。
- `Database` 中 `sessions`、`memories`、`core_memory_blocks` 仍是单租户设计；`messages` 通过 `session_id` 关联，不需要单独新增租户列，但所有 session 查询必须基于租户过滤。
- `MemoryManager` 与各 memory 子模块直接读全局表，没有请求级 namespace。
- `main.py` 当前只暴露 `/ws`，没有面向外部系统的同步 `/api/invoke`。

## Current State Analysis

### 已存在入口

- `backend/tars/main.py`
  - 注册了 `/ws` WebSocket 路由。
  - 已创建全局 `agent`、`memory_manager`、`db`、`connection_manager`。
- `backend/tars/channels/websocket.py`
  - `WebSocketChannel.handle_message()` 直接调用 `agent.handle_message(session_id, user_content, channel, file_ids)`。
  - 未携带 `tenant_id`。

### 已存在数据库能力

- `backend/tars/database/base.py`
  - `sessions` 表字段：`id/agent_id/user_id/title/created_at/updated_at/summary`
  - `messages` 表字段：`id/session_id/role/content/timestamp`
  - `memories` / `core_memory_blocks` 仍是全局数据。
  - `create_session/get_session/list_sessions/add_message/get_messages` 都不接受租户参数。

### 已存在记忆能力

- `backend/tars/memory/manager.py`
  - `MemoryManager` 持有 `core/archival/search/reflector`。
  - 当前方法不接受 `tenant_id` 或上下文。
- `backend/tars/memory/*`
  - 多处 SQL 直接查询 `memories` 或 `core_memory_blocks`，需要统一引入租户过滤。

### 已存在技能与工具

- `backend/tars/skills/loader.py` 与 `backend/tars/tools/dispatcher.py`
  - Phase 2 不需要实现 Pipeline 或结构化输出，只需保持接口兼容。

## Assumptions & Decisions

- 默认租户固定为 `default`，未显式传入租户时保持现有单用户行为。
- 本次只实现 Phase 2，不包含：
  - Skill Pipeline 编排
  - ToolDispatcher `response_format`
  - SKILL.md frontmatter 扩展
- `endpoints` 继续全局共享，不增加 `tenant_id`。
- 由于现有 `messages` 已通过 `session_id` 关联，Phase 2 不给 `messages` 加 `tenant_id` 字段。
- `MemoryManager` 采用“请求时绑定租户”的轻量模式，而不是为每个租户常驻一个完整 Agent。

## Proposed Changes

### 1. 新增 Tenant 上下文与缓存层

**Create:** `backend/tars/tenant/context.py`  
**Create:** `backend/tars/tenant/__init__.py`

实现内容：

- 定义 `TenantContext` dataclass：
  - `tenant_id: str`
  - `memory_manager: MemoryManager`
  - `session_id: str | None`
  - `metadata: dict`
- 定义 `TenantContextCache`
  - 使用 `OrderedDict` 做 LRU。
  - 默认容量 `100`。
  - 提供 `get_or_create(tenant_id, memory_factory)`、`touch(tenant_id)`、`evict_if_needed()`。
- `memory_factory` 返回“绑定到租户”的 `MemoryManager` 视图对象，而非创建独立 Agent。

原因：

- 将租户态与全局单例 Agent 解耦，避免在 Agent 内保存可变全局 `tenant_id`。

### 2. 给数据库表和 API 增加租户隔离基础

**Modify:** `backend/tars/database/base.py`

实现内容：

- 为 `sessions` 表增加 `tenant_id TEXT NOT NULL DEFAULT 'default'`。
- 为 `memories` 表增加 `tenant_id TEXT NOT NULL DEFAULT 'default'`。
- 将 `core_memory_blocks` 主键从 `name` 调整为复合唯一键 `(tenant_id, name)`：
  - 保持旧表兼容时，优先走迁移补列。
  - 新增 `tenant_id` 列并建立唯一索引 `idx_core_memory_tenant_name`。
- 添加索引：
  - `idx_sessions_tenant_updated`
  - `idx_memories_tenant_created`
  - `idx_memories_tenant_category`
- 将旧数据回填为 `tenant_id='default'`。

方法签名变更：

- `create_session(user_id="default", title="New Session", tenant_id="default")`
- `get_session(session_id: str, tenant_id: str = "default")`
- `list_sessions(user_id="default", tenant_id="default", limit=50)`
- `delete_session(session_id: str, tenant_id: str = "default")`
- `update_session_title(session_id: str, title: str, tenant_id: str = "default")`
- 需要保留 `messages` 方法签名，但读取 session 前先校验其租户归属。

原因：

- 让 Session 成为租户边界；messages 通过 session 间接隔离，memory 直接靠 `tenant_id` 隔离。

### 3. 让 Memory 层接受租户上下文

**Modify:** `backend/tars/memory/manager.py`  
**Modify:** `backend/tars/memory/core_memory.py`  
**Modify:** `backend/tars/memory/archival.py`  
**Modify:** `backend/tars/memory/search.py`  
**Modify:** `backend/tars/memory/reflector.py`  
**Modify:** `backend/tars/memory/archival_insert_tool.py`  
**Modify:** `backend/tars/memory/router.py`

实现内容：

- `MemoryManager` 增加：
  - `tenant_id` 属性，默认 `default`
  - `for_tenant(tenant_id: str) -> MemoryManager`
  - `set_tenant(tenant_id: str)`
- `CoreMemoryManager` 所有 SQL 追加 `tenant_id = ?`。
- `ArchivalManager/HybridSearch/Reflector` 对 `memories` 的查询和写入追加 `tenant_id`。
- `reflector.py` 中涉及 `SELECT/INSERT INTO memories`、`core_memory_blocks` 的地方必须透传租户。
- `archival_insert_tool.py` 作为全局工具，执行时默认写入 `default`；后续如支持租户工具调用，可从上下文注入。

原因：

- 保持现有 Memory API 结构不变，只在内部增加租户维度，避免大范围改写 Agent。

### 4. 让 Agent 主流程接受 TenantContext

**Modify:** `backend/tars/agent/agent.py`

实现内容：

- `handle_message()` 增加参数：
  - `tenant_context: Optional[TenantContext] = None`
  - `request_context: Optional[Dict[str, Any]] = None`
- 进入主流程时确定：
  - `tenant_id = tenant_context.tenant_id if tenant_context else "default"`
  - `memory_manager = tenant_context.memory_manager if tenant_context else self.memory_manager`
- 所有 session 读写改为调用带 `tenant_id` 的数据库方法。
- 记忆检索、反思、working context 查询使用租户绑定的 `memory_manager`。
- 保持原有 slash command / file_ids / channel 推送逻辑不变。

原因：

- 只在 Agent 入口增加上下文参数，不重写内部大部分能力。

### 5. WebSocket 改为租户路由

**Modify:** `backend/tars/channels/websocket.py`  
**Modify:** `backend/tars/main.py`

实现内容：

- 新 WebSocket 路由改为：
  - `/ws/{tenant_id}`
  - 保留 `/ws`，内部映射到 `default`
- `ConnectionManager.connect()` 与 `WebSocketChannel` 保存 `tenant_id`。
- `handle_message()` 调用 Agent 时注入 `tenant_context`。
- `main.py` 中从全局 `tenant_context_cache` 获取上下文。

原因：

- 保持前端兼容的同时，让外部或未来多租户前端能显式指定租户。

### 6. 新增 REST `/api/invoke`

**Create:** `backend/tars/api/invoke.py`  
**Modify:** `backend/tars/api/__init__.py`  
**Modify:** `backend/tars/main.py`

实现内容：

- 定义请求模型：
  - `message: str`
  - `session_id: Optional[str]`
  - `context: Dict[str, Any] = {}`
  - `stream: bool = False`
- Header:
  - `X-Tenant-Id`，默认 `default`
  - `Authorization` 先做透传解析，Phase 2 仅校验“有值即可”或复用现有 API key 校验工具；如现有鉴权未统一，先以最小兼容方案实现并在文档说明。
- `stream=False`
  - 使用内存 channel 收集 `text_chunk` / `done` / `error`
  - 返回 `{response, session_id, tool_calls, usage}`
- `stream=True`
  - 返回 `StreamingResponse` + SSE
  - 复用同一个 collector channel，边接收边产出 event

原因：

- 让外部系统能直接同步调用同一套 Agent 主流程，而不是复制一份推理逻辑。

### 7. 新增入口层的租户解析辅助

**Create:** `backend/tars/tenant/middleware.py`

实现内容：

- 提供纯函数：
  - `resolve_tenant_id_from_header(headers) -> str`
  - `resolve_tenant_id_from_ws_path(path_params) -> str`
- 可选提供 `get_tenant_context(cache, tenant_id, memory_manager)` 帮助函数。
- 本次不强制注册 FastAPI middleware class；优先采用轻量 helper，降低侵入性。

原因：

- spec 写的是 middleware，但当前代码结构更适合先做入口 helper，保留后续升级空间。

## File Change Map

- `backend/tars/tenant/context.py`
  - 新增租户上下文与 LRU 缓存。
- `backend/tars/tenant/middleware.py`
  - 新增租户解析 helper。
- `backend/tars/api/invoke.py`
  - 新增 REST invoke 接口和同步/SSE 输出适配。
- `backend/tars/database/base.py`
  - 新增租户字段、迁移逻辑、按租户查询方法。
- `backend/tars/memory/manager.py`
  - 增加租户绑定能力。
- `backend/tars/memory/core_memory.py`
  - core memory 按租户隔离。
- `backend/tars/memory/archival.py`
  - archival 写入按租户隔离。
- `backend/tars/memory/search.py`
  - 检索按租户过滤。
- `backend/tars/memory/reflector.py`
  - 反思写入按租户过滤。
- `backend/tars/memory/router.py`
  - 记忆路由检索按租户过滤。
- `backend/tars/memory/archival_insert_tool.py`
  - 显式设置默认租户写入。
- `backend/tars/agent/agent.py`
  - `handle_message()` 接受 `TenantContext`。
- `backend/tars/channels/websocket.py`
  - 注入租户上下文。
- `backend/tars/api/sessions.py`
  - 读取 `X-Tenant-Id`，列表/创建/读取消息按租户过滤。
- `backend/tars/main.py`
  - 初始化 tenant cache，注册 `/api/invoke` 和 `/ws/{tenant_id}`。

## Verification Steps

### 手工验证

1. 启动后端：
   - `cd /Users/daobanxiang/myproject/TARS/backend`
   - `python3 -m uvicorn tars.main:app --reload`
2. 验证默认租户 WebSocket 兼容：
   - 旧 `/ws` 连接仍能聊天。
3. 验证显式租户隔离：
   - 分别连接 `/ws/tenant_a` 和 `/ws/tenant_b`
   - 在两个租户中创建不同 session/message
   - 确认互相看不到对方 session。
4. 验证 `/api/invoke`：
   - `POST /api/invoke`
   - header 带 `X-Tenant-Id: tenant_a`
   - 返回 `response/session_id`
5. 验证 memory 隔离：
   - 在 `tenant_a` 写入记忆
   - `tenant_b` 对同 query 不应检索到该记忆。

### 自动化检查

- Python 语法检查：
  - `python3 -m compileall /Users/daobanxiang/myproject/TARS/backend/tars`
- 若已有测试框架：
  - 为数据库租户过滤、`/api/invoke`、`TenantContextCache` 添加聚焦单测。
- 变更后运行 `GetDiagnostics` 检查新增/修改文件。

## Execution Order

1. 先改 `database/base.py` 与迁移逻辑。
2. 新增 `tenant/` 模块。
3. 改 `memory/*` 以支持租户。
4. 改 `agent/agent.py` 接入 `TenantContext`。
5. 改 `websocket.py` 与 `main.py`。
6. 新增 `/api/invoke`。
7. 最后补 sessions API 的租户 header 支持与验证。
