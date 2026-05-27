---
doc_type: spec
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# TARS 核心大脑扩展架构设计

## 核心决策

1. **产品型多租户**：TARS 作为产品 AI 后端，服务多个租户
2. **Skill 包模式**：垂直场景作为 Skill 包注册，共享进程，namespace 隔离
3. **共享能力，隔离数据**：所有租户共享 skill/tool，记忆/会话各自独立
4. **REST 同步调用**：新增 `/api/invoke` 供外部系统集成
5. **Tenant Context 注入**：单 Agent 实例 + Context 切换，轻量高效

## 整体架构

```
┌─────────────────────────────────────────────────┐
│                   入口层                          │
│  WebSocket /ws/{tenant_id}                       │
│  REST POST /api/invoke                           │
├─────────────────────────────────────────────────┤
│              TenantMiddleware                     │
│  解析 tenant_id → 创建/复用 TenantContext         │
├─────────────────────────────────────────────────┤
│              Agent (单实例)                       │
│  接收 TenantContext → 切换数据视图 → 处理请求      │
├──────────┬──────────┬───────────┬───────────────┤
│ Memory   │ Session  │ Skill     │ Tool          │
│ (按租户)  │ (按租户)  │ (全局共享) │ (全局共享)     │
├──────────┴──────────┴───────────┴───────────────┤
│              Storage Layer                        │
│  SQLite/PostgreSQL (tenant_id 字段隔离)           │
└─────────────────────────────────────────────────┘
```

## TenantContext

```python
@dataclass
class TenantContext:
    tenant_id: str
    memory_manager: MemoryManager
    session_id: str | None
    metadata: dict  # 租户级配置（模型偏好等）
```

- 生命周期：请求开始创建/从缓存取出，请求结束放回缓存
- 缓存策略：LRU，最大 100 个活跃 Context，超出淘汰最久未用
- MemoryManager 内部查询自动加 `WHERE tenant_id = ?`
- 默认租户 `tenant_id = "default"` 用于单用户/本地开发，向后兼容

## REST 同步调用接口

```
POST /api/invoke
Headers:
  X-Tenant-Id: "tenant_abc"
  Authorization: Bearer <api_key>

Body:
{
  "message": "帮我分析这份报告",
  "session_id": "optional_session_id",
  "context": {},
  "stream": false
}

Response:
{
  "response": "分析结果...",
  "session_id": "sess_xxx",
  "tool_calls": [...],
  "usage": { "model": "...", "tokens": ... }
}
```

- 与 WebSocket 共享 `Agent.handle_message()` 逻辑
- `stream: false` 同步等待完整响应
- `stream: true` 走 SSE 流式返回

## 数据隔离方案

现有表加 `tenant_id` 字段，不新建表：

| 表 | 隔离方式 |
|---|---|
| sessions | `tenant_id` 字段 |
| messages | 通过 session 关联 |
| archival_memory | `tenant_id` 字段 |
| core_memory | `tenant_id` 字段（每租户独立 4 块） |
| endpoints（模型配置） | 全局共享，不按租户隔离 |

## Skill 编排层

### Skill 声明增强

```yaml
# SKILL.md frontmatter 新增
depends_on: [web_search, file_read]
outputs:
  type: json
  schema: { ... }
```

### Skill Pipeline

```yaml
# pipelines/report_analysis.yaml
name: report_analysis
steps:
  - skill: web_search
    input: "{query}"
    output_as: search_results
  - skill: document_parser
    input: "{file}"
    output_as: parsed_doc
  - skill: analysis
    input:
      context: "{search_results}"
      document: "{parsed_doc}"
    output_as: final_report
```

- Pipeline 是 skill 的有序组合，声明式定义
- Agent 识别匹配意图时自动编排
- 也可显式触发：`POST /api/invoke { "pipeline": "report_analysis", ... }`

## 结构化输出

ToolDispatcher 层新增 `response_format` 支持：

```python
response_format = {
    "type": "json_schema",
    "schema": { ... }
}
```

- 垂直 skill 声明输出 schema → LLM 调用时注入约束
- 不支持 JSON mode 的模型降级为 prompt 约束 + 后处理解析

## 文件变更

### 新增

| 文件 | 职责 |
|------|------|
| `backend/tars/tenant/context.py` | TenantContext + LRU 缓存 |
| `backend/tars/tenant/middleware.py` | 请求级租户解析 |
| `backend/tars/api/invoke.py` | REST /api/invoke 路由 |
| `backend/tars/skills/pipeline.py` | Skill Pipeline 编排引擎 |

### 修改

| 文件 | 变更 |
|------|------|
| `database/*.py` | 表加 tenant_id，查询加过滤 |
| `memory/manager.py` | 接受 TenantContext，namespace 隔离 |
| `agent/agent.py` | handle_message 接受 TenantContext |
| `channels/websocket.py` | URL path 解析 tenant_id |
| `tools/dispatcher.py` | 支持 response_format 透传 |
| `skills/loader.py` | 解析 pipeline YAML |
| `main.py` | 注册新路由，初始化 tenant 缓存 |

## 实施优先级

```
Phase 1: 模型配置重构（spec 已完成）
Phase 2: TenantContext + 数据隔离 + REST API
Phase 3: Skill Pipeline 编排
Phase 4: 结构化输出
```

Phase 2 完成后即可接入垂直业务。Phase 3/4 按需迭代。
