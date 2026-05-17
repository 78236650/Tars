# TARS v4.0.0 "Hardened Base" — 建设方案

## 方案制定日期: 2026-05-17
## 当前版本: v3.9.1
## 目标版本: v4.0.0
## 版本代号: Hardened Base（底座加固）

---

## 一、项目定位与决策背景

### 1.1 产品定位

**通用本地 AI Agent 平台**，部署于内网服务器，支持多用户并发使用。用户通过技能/插件适配自己的垂直场景。

### 1.2 部署环境

- 内网服务器（多用户共享）
- LLM Provider：Ollama 本地模型 + 国内云端 API（阿里/DeepSeek 等）
- 不发布 PyPI，部署方式为 git clone + Docker

### 1.3 借鉴来源

基于 Hermes Agent v0.13-v0.14 研究，**选择性借鉴**：

| Hermes 特性 | TARS 决策 | 理由 |
|------------|----------|------|
| 安全加固体系 | ✅ 采纳 | 多用户内网刚需 |
| 性能优化（连接复用/启动优化） | ✅ 采纳 | 多用户并发直接受益 |
| Provider 插件化 | ✅ 采纳 | 用多种 Provider，核心扩展点 |
| Lazy Install / Debloating | ⚠️ 简化为模块化启动 | 不需要 PyPI，按配置启用/禁用即可 |
| Skill Curator | ⚠️ 简化为使用统计 | 内网技能数量有限，手动管理够用 |
| PyPI 发布 | ❌ 不做 | 内网部署用 git clone / Docker |
| OpenAI-compatible Proxy | ❌ 不做 | 非核心，v4.1 再议 |
| 多智能体 Kanban | ❌ 不做 | 探索性太强，当前子代理够用 |
| Checkpoints 状态持久化 | ❌ 不做 | 现有 PDCA paused 恢复机制够用 |

### 1.4 新增（原方案缺失，内网多用户刚需）

| 功能 | 理由 |
|------|------|
| 审计日志 | 内网合规，谁在什么时候做了什么 |
| 多用户资源隔离 | 防止单用户占满资源 |
| 并发限流 | 多用户同时调用 LLM 时的队列管理 |
| 记忆权限管理 | 用户记忆隔离 + 共享记忆 + 管理员管控 |

---

## 二、整体架构

```
Phase 1: Security Hardening（安全加固）
├── 1.1 敏感信息脱敏引擎
├── 1.2 多用户权限隔离增强
├── 1.3 审计日志系统
├── 1.4 提示词注入防护
└── 1.5 记忆权限管理

Phase 2: Performance（性能革命）
├── 2.1 启动优化（延迟导入 + 并行初始化）
├── 2.2 LLM 连接复用池
├── 2.3 Prompt Cache
└── 2.4 多用户并发资源管理

Phase 3: Provider Plugin Architecture（Provider 插件化）
├── 3.1 ProviderBase 抽象接口
├── 3.2 ProviderRegistry（发现 + 注册）
├── 3.3 OpenAI Compatible 统一层
├── 3.4 内置 Provider 迁移
└── 3.5 配置化 + 热切换

Phase 4: Platform Polish（平台收尾）
├── 4.1 模块化启动
├── 4.2 Skill Curator 简化版
└── 4.3 集成测试 + 文档
```

### 实施依赖关系

```
Phase 1 ──┐
           ├──→ Phase 3（依赖 Phase 2 连接池）──→ Phase 4
Phase 2 ──┘
```

Phase 1 和 Phase 2 可并行推进。

---

## 三、Phase 1 — Security Hardening（安全加固）

### 3.1 敏感信息脱敏引擎

#### 目标

对话历史、日志、API 响应中自动检测并脱敏敏感信息。

#### 文件结构

```
backend/tars/security/
├── __init__.py
├── sanitizer.py      # 脱敏引擎核心
├── patterns.py       # 正则模式库
├── config.py         # 脱敏策略配置
├── memory_permission.py  # 记忆权限检查
└── injection_guard.py    # 提示词注入防护
```

#### 工作机制

- **拦截点**：Agent 输出前 + 日志写入前 + API 响应前
- **检测模式**：
  - API Key（`sk-*`、`key-*`、`Bearer *`）
  - 手机号（11位数字，1开头）
  - 邮箱地址
  - 银行卡号（16-19位数字）
  - 密码字段（JSON 中 key 含 password/secret/token）
  - 私钥块（`-----BEGIN * PRIVATE KEY-----`）
- **脱敏策略**：
  - 默认：部分隐藏（`138****1234`、`sk-****abcd`）
  - 可配置：完全替换（`[REDACTED]`）
- **白名单**：管理员可标记特定会话为"不脱敏"（调试用）

#### 集成方式

作为中间件挂在 Agent 输出管道，不侵入 Agent 核心逻辑：
```python
# channel.send() 前统一过 sanitizer
async def send_sanitized(session_id, payload):
    payload["content"] = sanitizer.sanitize(payload.get("content", ""))
    await channel.send(session_id, payload)
```

#### 涉及文件

- `backend/tars/security/sanitizer.py`（新建）
- `backend/tars/security/patterns.py`（新建）
- `backend/tars/channels/__init__.py`（集成脱敏中间件）

---

### 3.2 多用户权限隔离增强

#### 当前问题

- admin/user/guest 三级角色存在，但工具层面没有按用户隔离
- shell/file_write 工具没有限制用户可操作的目录范围
- 不同用户的会话数据理论上可以交叉访问

#### 设计

| 层级 | 隔离内容 | 实现方式 |
|------|---------|---------|
| 数据隔离 | 会话、记忆、文件 | tenant_id 贯穿所有 DB 查询（已有基础） |
| 文件隔离 | 每用户独立 workspace | `~/.tars/workspaces/{tenant_id}/`，WorkspaceSandbox 强制限制 |
| 工具隔离 | 危险工具按角色开放 | PermissionEngine 扩展：`role → allowed_tools` 映射 |
| 资源隔离 | 并发请求数 | 每用户 LLM 请求队列，默认 max_concurrent=2 |

#### 二次确认增强

- **shell 工具**：非白名单命令一律需要确认（当前只拦截黑名单，改为白名单模式）
- **file_write**：写入 workspace 外的路径需要确认
- **确认方式**：WebSocket 推送确认请求，前端弹窗，超时 60s 自动拒绝

#### 工具权限映射

```yaml
# config/tool_permissions.yaml
roles:
  admin:
    allowed_tools: "*"
    workspace_restriction: false
  user:
    allowed_tools:
      - weather
      - web_search
      - web_fetch
      - file          # 只读
      - file_write    # 限制在 workspace 内
      - python_exec
      - memory
      - task_planner
    denied_tools:
      - shell         # 需要 admin 单独授权
      - process
      - network
    workspace_restriction: true
  guest:
    allowed_tools:
      - weather
      - web_search
    workspace_restriction: true
```

#### 涉及文件

- `backend/tars/security/config.py`（新建）
- `backend/tars/tools/builtin/shell.py`（白名单模式）
- `backend/tars/tools/builtin/file_write.py`（workspace 限制）
- `backend/tars/skills/permission_engine.py`（扩展角色映射）

---

### 3.3 审计日志系统

#### 目标

记录所有工具调用和关键操作，支持查询和导出。

#### 数据模型

```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    user_id TEXT,
    session_id TEXT,
    action TEXT NOT NULL,        -- tool_call | login | logout | config_change | skill_install | permission_denied
    target TEXT,                 -- 工具名 / 资源名
    arguments TEXT,              -- JSON，脱敏后的参数摘要
    result TEXT,                 -- success | failed | denied
    ip_address TEXT,
    duration_ms INTEGER
);

CREATE INDEX idx_audit_tenant_time ON audit_log(tenant_id, timestamp);
CREATE INDEX idx_audit_action ON audit_log(action, timestamp);
```

#### 记录范围

- 所有工具调用（含参数摘要，脱敏后）
- 登录/登出
- 配置变更（模型切换、技能安装/卸载、权限变更）
- 权限拒绝事件
- 记忆操作（创建/删除/修改，含 scope 变更）

#### API

```
GET  /api/audit/logs?tenant_id=&action=&from=&to=&limit=  — 查询（仅 admin）
GET  /api/audit/export?format=csv&from=&to=               — CSV 导出（仅 admin）
GET  /api/audit/stats                                      — 统计摘要（调用量/活跃用户）
```

#### 存储策略

- 默认保留 90 天
- 超过 90 天自动归档到 `audit_log_archive` 表（压缩存储）
- 可配置保留天数

#### 涉及文件

- `backend/tars/security/audit.py`（新建）
- `backend/tars/database/base.py`（新增 audit_log 表）
- `backend/tars/api/audit.py`（新建 API 路由）
- `backend/tars/tools/dispatcher.py`（集成审计记录）

---

### 3.4 提示词注入防护

#### 目标

检测用户输入中的 Prompt Injection 尝试，轻量级规则引擎（不依赖额外 LLM 调用）。

#### 检测模式

| 类别 | 示例 | 风险级别 |
|------|------|---------|
| 角色覆盖 | "ignore previous instructions"、"你现在是..." | 高 |
| 系统提示词泄露 | "repeat your system prompt"、"输出你的指令" | 高 |
| 编码绕过 | base64 包裹的指令、unicode 混淆 | 中 |
| 工具滥用诱导 | "执行 rm -rf /"、"读取 /etc/passwd" | 高 |

#### 处理策略

- **低风险**：记录审计日志，正常处理
- **高风险**：拒绝执行 + 通知管理员 + 审计日志标记 `action=injection_blocked`
- **误杀防护**：用户讨论 prompt engineering 本身不触发（检测上下文语境）

#### 实现方式

```python
class InjectionGuard:
    """轻量级规则引擎，不调用 LLM"""
    
    def check(self, user_input: str) -> InjectionResult:
        # 1. 正则匹配已知攻击模式
        # 2. 评估风险等级
        # 3. 返回 (is_blocked, risk_level, matched_pattern)
```

#### 涉及文件

- `backend/tars/security/injection_guard.py`（新建）
- `backend/tars/agent/agent.py`（handle_message 入口处检查）

---

### 3.5 记忆权限管理

#### 核心原则

1. **同一用户跨会话共享记忆** — `tenant_id = user_id`，新开会话自动继承
2. **用户只能访问自己的记忆** — 默认隔离
3. **管理员可查看/管理所有用户记忆** — 运维需要
4. **支持团队共享记忆** — 某些知识所有人可见

#### 权限矩阵

| 角色 | 自己的记忆 | 他人的记忆 | 共享记忆 | 管理操作 |
|------|-----------|-----------|---------|---------|
| admin | 读/写/删 | 读/删 | 读/写/删 | 创建共享、强制清理 |
| user | 读/写/删 | 无 | 只读 | 无 |
| guest | 只读 | 无 | 只读 | 无 |

#### 记忆作用域

```python
class MemoryScope(Enum):
    PRIVATE = "private"    # 仅本用户可见（默认）
    SHARED = "shared"      # 所有用户可读，仅 admin 可写
```

#### 数据库变更

```sql
ALTER TABLE memories ADD COLUMN scope TEXT NOT NULL DEFAULT 'private';
ALTER TABLE core_memory_blocks ADD COLUMN scope TEXT NOT NULL DEFAULT 'private';
```

#### 权限检查器

```python
# backend/tars/security/memory_permission.py

class MemoryPermission:
    def can_read(self, actor: User, target_tenant_id: str, scope: MemoryScope) -> bool:
        if actor.id == target_tenant_id:
            return True
        if scope == MemoryScope.SHARED:
            return True
        return actor.role == UserRole.ADMIN

    def can_write(self, actor: User, target_tenant_id: str, scope: MemoryScope) -> bool:
        if actor.role == UserRole.GUEST:
            return False
        if actor.id == target_tenant_id and scope == MemoryScope.PRIVATE:
            return True
        return actor.role == UserRole.ADMIN

    def can_delete(self, actor: User, target_tenant_id: str, scope: MemoryScope) -> bool:
        return self.can_write(actor, target_tenant_id, scope)
```

#### System Prompt 记忆注入逻辑

```
组装顺序：
1. persona（用户私有 core_memory.persona）
2. shared_context（共享 core_memory，如团队 project_context）
3. user_profile（用户私有 core_memory.user_profile）
4. working_principles（用户私有）
5. archival recall（查询范围：用户私有 + shared）
```

记忆检索 SQL：
```sql
SELECT * FROM memories
WHERE (tenant_id = ? OR scope = 'shared')
  AND ...
```

#### Admin 记忆管理 API

```
GET    /api/admin/memory/users                    — 所有用户记忆统计
GET    /api/admin/memory/users/{user_id}          — 指定用户记忆详情
DELETE /api/admin/memory/users/{user_id}/purge     — 清空指定用户全部记忆
POST   /api/admin/memory/shared                   — 创建/更新共享记忆
DELETE /api/admin/memory/shared/{memory_id}        — 删除共享记忆
```

#### 涉及文件

- `backend/tars/security/memory_permission.py`（新建）
- `backend/tars/database/base.py`（ALTER TABLE 加 scope 字段）
- `backend/tars/memory/core_memory.py`（集成权限检查）
- `backend/tars/memory/archival.py`（检索范围加 shared）
- `backend/tars/memory/manager.py`（注入逻辑调整）
- `backend/tars/api/memory.py`（API 层权限拦截）
- `backend/tars/api/admin.py`（新建 admin 管理 API）

---

## 四、Phase 2 — Performance（性能革命）

### 4.1 启动优化

#### 当前问题

- 所有模块在 `main.py` 启动时同步加载（memory、skills、tools、models 全部初始化）
- embedding 模型加载耗时长（sentence-transformers）
- 技能扫描目录 I/O 阻塞

#### 优化策略

| 手段 | 预期收益 | 实现方式 |
|------|---------|---------|
| 延迟导入 | 启动时间 -40% | 重型模块（embedding、OCR、pandas）移到首次使用时 import |
| 并行初始化 | 启动时间 -30% | DB、SkillRegistry、ToolRegistry 用 `asyncio.gather` 并行 |
| 配置缓存 | 二次启动 -50% | 技能扫描结果缓存到 `~/.tars/cache/skills_manifest.json`，文件 mtime 未变则跳过重扫 |

#### 实现

```python
# backend/tars/lazy.py

def lazy_import(module_path: str):
    """延迟导入装饰器，首次访问时才 import"""
    # 用于 sentence_transformers、pandas、Pillow、pytesseract 等重型依赖
```

启动流程重排：
```
1. 同步：DB 连接 + 配置加载（必须最先）
2. 并行：asyncio.gather(
     ToolRegistry.init(),
     SkillRegistry.init(use_cache=True),
     MemoryManager.init_light(),  # 不加载 embedding 模型
   )
3. 延迟：embedding 模型在首次记忆检索时加载
4. 延迟：OCR/PDF 解析器在首次文件上传时加载
```

#### 涉及文件

- `backend/tars/main.py`（启动流程重排）
- `backend/tars/lazy.py`（新建）
- `backend/tars/memory/embeddings.py`（延迟加载）
- `backend/tars/skills/loader.py`（缓存机制）

---

### 4.2 LLM 连接复用池

#### 当前问题

- 每次 `OllamaProvider.chat()` 新建 httpx 连接
- 多用户并发时连接数爆炸
- 云端 API 同样每次新建，浪费 TCP 握手 + TLS 时间

#### 设计

```python
# backend/tars/models/connection_pool.py

class LLMConnectionPool:
    """Provider 级别的 httpx.AsyncClient 复用"""
    
    # 池化策略：
    # - key: provider_type + base_url（如 "ollama:http://localhost:11434"）
    # - 每个 key 维护一个 httpx.AsyncClient 实例
    # - max_connections: 可配置，默认 10
    # - max_keepalive_connections: 5
    # - keepalive_expiry: 300s
    # - timeout: connect=5s, read=120s（LLM 生成慢）
    
    def get_client(self, provider_key: str) -> httpx.AsyncClient: ...
    def close_all(self): ...  # 服务关闭时调用
    def health_check(self): ...  # 空闲超 5 分钟的连接回收
```

#### 集成方式

- `OllamaProvider` / `CustomProvider` / `OpenRouterProvider` 构造时从池中获取 client
- 服务 shutdown 事件中统一 `pool.close_all()`
- 定时健康检查（每 5 分钟）

#### 预期收益

- 多用户并发 LLM 调用延迟降低 30-50%（省去 TCP 握手 + TLS）
- 连接数可控，不会因并发打爆 Ollama

#### 涉及文件

- `backend/tars/models/connection_pool.py`（新建）
- `backend/tars/models/ollama.py`（使用连接池）
- `backend/tars/models/custom.py`（使用连接池）
- `backend/tars/models/openrouter.py`（使用连接池）

---

### 4.3 Prompt Cache

#### 当前问题

- 每次对话重新拼装 System Prompt（persona + core memory + skills + tools schema）
- 相同用户连续对话，System Prompt 99% 不变但每次重算
- 字符串拼接 + JSON 序列化开销在高并发下累积

#### 设计

```python
# backend/tars/cache/prompt_cache.py

class PromptCache:
    """System Prompt 组件级缓存"""
    
    # 缓存粒度与 TTL：
    # ┌─────────────────────┬──────────────┬─────────────────────────┐
    # │ 组件                 │ 缓存 key     │ TTL / 失效条件           │
    # ├─────────────────────┼──────────────┼─────────────────────────┤
    # │ tools_schema         │ 全局         │ 永不过期（重启才变）      │
    # │ persona_block        │ tenant_id    │ 1h / workspace 变更时    │
    # │ core_memory_block    │ session_id   │ 60s / core_memory 写入时 │
    # │ skills_prompt        │ session+skills│ 60s / 技能激活变更时     │
    # │ shared_memory_block  │ 全局         │ 5min / admin 修改时      │
    # └─────────────────────┴──────────────┴─────────────────────────┘
    
    def get_or_build(self, key: str, builder: Callable, ttl: int) -> str: ...
    def invalidate(self, key_pattern: str): ...  # 支持通配符失效
```

#### 失效机制

- **主动失效**：core_memory_append/replace 操作后清除对应 session 缓存
- **被动失效**：TTL 过期自动清除
- **全局失效**：技能安装/卸载时清除所有 skills_prompt 缓存

#### 预期收益

- System Prompt 拼装时间从 ~50ms 降到 <5ms（缓存命中时）
- 减少重复字符串拼接的内存分配
- 高并发下 CPU 占用显著降低

#### 涉及文件

- `backend/tars/cache/__init__.py`（新建）
- `backend/tars/cache/prompt_cache.py`（新建）
- `backend/tars/agent/agent.py`（使用缓存拼装 system prompt）
- `backend/tars/memory/core_memory.py`（写入时触发失效）

---

### 4.4 多用户并发资源管理

#### 当前问题

- 多用户同时发消息，所有请求直接打到 LLM，无排队
- 本地 Ollama 通常只能并行 1-2 个请求，多了会 OOM 或超时
- 云端 API 有 rate limit，无保护直接 429

#### 设计

```python
# backend/tars/concurrency/limiter.py

class LLMRateLimiter:
    """Provider 级别的并发控制 + 公平调度"""
    
    # 实现：asyncio.Semaphore + 公平队列（FIFO per tenant）
    # 防止单用户独占：per_user_max 限制
    # 超时处理：排队超时返回友好提示
    
    async def acquire(self, tenant_id: str, provider_key: str) -> bool: ...
    def release(self, tenant_id: str, provider_key: str): ...
```

#### 配置

```yaml
# config/concurrency.yaml
providers:
  ollama:
    max_concurrent: 2        # Ollama 全局最大并发
    per_user_max: 1          # 单用户最多占 1 个槽位
    queue_timeout: 60        # 排队超时秒数
    queue_max_size: 20       # 队列最大长度
  custom:
    max_concurrent: 5        # 云端 API 全局最大并发
    per_user_max: 2
    queue_timeout: 30
    queue_max_size: 50
```

#### 用户体验

- 排队时：WebSocket 推送 `{"type": "queued", "position": 3, "estimated_wait": 15}`
- 超时时：返回 `{"type": "error", "message": "系统繁忙，请稍后重试", "code": "rate_limited"}`
- 前端展示排队状态（"前面还有 2 人..."）

#### 涉及文件

- `backend/tars/concurrency/__init__.py`（新建）
- `backend/tars/concurrency/limiter.py`（新建）
- `backend/tars/agent/agent.py`（handle_message 中 acquire/release）
- `frontend/src/components/chat/QueueStatus.vue`（新建，排队提示）

---

## 五、Phase 3 — Provider Plugin Architecture（Provider 插件化）

### 5.1 当前问题

```
backend/tars/models/
├── __init__.py      # LLMProvider 基类 + OllamaProvider 导出
├── ollama.py        # Ollama 实现（硬编码）
├── openrouter.py    # OpenRouter 实现（硬编码）
└── custom.py        # Custom/阿里/Kimi（硬编码）
```

- 三个 Provider 硬编码，新增需改源码
- 没有统一配置格式
- 切换 Provider 需重启或手动调用
- 用户无法自行扩展（vLLM、LocalAI、LM Studio）

### 5.2 目标架构

```
backend/tars/models/
├── base.py              # ProviderBase 抽象基类
├── registry.py          # ProviderRegistry（发现 + 注册 + 实例管理）
├── connection_pool.py   # 连接复用池（Phase 2 产出）
├── plugins/             # 内置 Provider 插件
│   ├── __init__.py
│   ├── ollama.py        # Ollama Provider
│   ├── openrouter.py    # OpenRouter Provider
│   └── openai_compat.py # 通用 OpenAI 兼容（合并 custom.py）
└── __init__.py          # 向后兼容导出

用户自定义位置：
~/.tars/providers/
└── my_vllm.py           # 用户自己写的 Provider
```

### 5.3 ProviderBase 抽象接口

```python
# backend/tars/models/base.py

from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional
from dataclasses import dataclass

@dataclass
class ModelInfo:
    id: str
    name: str
    supports_tools: bool = False
    supports_vision: bool = False
    context_length: int = 4096

@dataclass
class ChatResponse:
    content: str
    tool_calls: Optional[List[dict]] = None
    usage: Optional[dict] = None
    model: str = ""

class ProviderBase(ABC):
    """所有 LLM Provider 的基类"""
    
    # 元信息（插件发现用）
    name: str                    # "ollama" | "openrouter" | "openai_compat"
    display_name: str            # "Ollama (Local)" | "阿里云 DashScope"
    auth_type: str               # "none" | "api_key" | "oauth"
    
    @abstractmethod
    async def chat(self, messages: list, tools: list = None, **kwargs) -> ChatResponse: ...
    
    @abstractmethod
    async def stream_chat(self, messages: list, tools: list = None, **kwargs) -> AsyncIterator: ...
    
    @abstractmethod
    async def list_models(self) -> List[ModelInfo]: ...
    
    def supports_tools(self, model: str) -> bool: ...
    def supports_vision(self, model: str) -> bool: ...
```

### 5.4 ProviderRegistry

```python
# backend/tars/models/registry.py

class ProviderRegistry:
    """Provider 发现、注册、实例管理"""
    
    # 发现顺序：
    # 1. backend/tars/models/plugins/*.py（内置）
    # 2. ~/.tars/providers/*.py（用户自定义）
    
    # 注册约定：每个 .py 文件导出 __provider_class__ 变量
    
    def discover(self): ...                              # 扫描并注册所有 Provider
    def list_providers(self) -> List[ProviderInfo]: ...  # 列出可用 Provider
    def get_instance(self, name: str, config: dict) -> ProviderBase: ...  # 获取实例
    def hot_reload(self, name: str): ...                 # 不重启更新 Provider
```

### 5.5 OpenAI Compatible 统一层

当前 `custom.py` 和 `openrouter.py` 本质都是 OpenAI 兼容协议。合并为一个通用实现：

```python
# backend/tars/models/plugins/openai_compat.py

class OpenAICompatProvider(ProviderBase):
    """通用 OpenAI 兼容 Provider"""
    
    name = "openai_compat"
    display_name = "OpenAI Compatible"
    auth_type = "api_key"
    
    # 配置驱动，不同厂商只是配置不同：
    # - base_url
    # - api_key
    # - model_list（或通过 /v1/models 自动发现）
    # - quirks（厂商特殊行为适配）
    
    # quirks 适配器：
    # - tool_call_nested: true  → 阿里 DashScope 嵌套格式展平
    # - no_stream_tools: true   → 工具调用时强制非流式
    # - model_prefix: "openai/" → OpenRouter 模型名前缀
```

### 5.6 配置格式

```yaml
# config/providers.yaml

providers:
  - name: ollama-local
    type: ollama
    base_url: http://localhost:11434
    default_model: qwen3:8b
    
  - name: aliyun-dashscope
    type: openai_compat
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key: ${DASHSCOPE_API_KEY}
    default_model: qwen-max
    quirks:
      tool_call_nested: true
      
  - name: deepseek
    type: openai_compat
    base_url: https://api.deepseek.com/v1
    api_key: ${DEEPSEEK_API_KEY}
    default_model: deepseek-chat

  - name: openrouter
    type: openai_compat
    base_url: https://openrouter.ai/api/v1
    api_key: ${OPENROUTER_API_KEY}
    default_model: anthropic/claude-3.5-sonnet
    quirks:
      model_prefix: true

# 默认 Provider（启动时使用）
default_provider: ollama-local
```

### 5.7 向后兼容

- `from ..models import OllamaProvider, LLMProvider` 导入路径保持不变
- 现有环境变量（`OLLAMA_MODEL`、`OPENROUTER_API_KEY`）继续生效
- 首次启动时如果没有 `providers.yaml`，从旧配置自动生成
- 迁移脚本：`scripts/migrate_providers.py`

### 5.8 热切换

- 前端模型切换 → API 调用 → ProviderRegistry 返回对应实例
- 不需要重启服务
- 连接池按 provider_key 隔离，切换不影响其他用户的连接
- 切换事件记入审计日志

### 5.9 前端适配

- 模型选择页面：按 Provider 分组展示可用模型
- 每个 Provider 显示连接状态（在线/离线/错误）
- 支持在线测试连接（`POST /api/providers/{name}/test`）

#### 涉及文件

- `backend/tars/models/base.py`（重构为 ProviderBase）
- `backend/tars/models/registry.py`（新建）
- `backend/tars/models/plugins/ollama.py`（从 models/ollama.py 迁移）
- `backend/tars/models/plugins/openai_compat.py`（合并 custom + openrouter）
- `backend/tars/models/__init__.py`（向后兼容导出）
- `config/providers.yaml`（新建配置文件）
- `scripts/migrate_providers.py`（新建迁移脚本）
- `frontend/src/views/ModelsView.vue`（按 Provider 分组）

---

## 六、Phase 4 — Platform Polish（平台收尾）

### 6.1 模块化启动

#### 目标

不需要的功能模块不加载，减少资源占用，加快启动。

#### 配置

```yaml
# config/modules.yaml

modules:
  # 核心模块（始终加载，不可禁用）
  core:
    - agent
    - tools
    - skills
    - memory
    - auth
    - security

  # 可选模块（按需启用）
  optional:
    meeting:
      enabled: false
      description: "会议助手（录音转写 + 摘要）"
      dependencies: [whisper, ffmpeg]
      routes: ["/api/meeting/*"]
      
    bi:
      enabled: false
      description: "BI 工作台（数据分析 + 可视化）"
      dependencies: [pandas, matplotlib]
      routes: ["/api/bi/*"]
      
    knowledge:
      enabled: true
      description: "知识库（文档解析 + RAG）"
      dependencies: [pypdf, python-docx]
      routes: ["/api/knowledge/*"]
      
    skillhub:
      enabled: true
      description: "SkillHub 技能市场"
      dependencies: []
      routes: ["/api/skillhub/*"]
```

#### 实现方式

- `main.py` 启动时读取 `modules.yaml`，只注册 `enabled: true` 的模块路由
- 未启用模块的 API 返回 `404 {"error": "module_disabled", "module": "bi"}`
- 前端通过 `GET /api/modules` 获取启用状态，动态显示/隐藏侧栏入口
- 依赖检查：启用模块时检查 Python 依赖是否已安装，未安装则提示

#### 与 Phase 2 的关系

- Phase 2 解决"加载慢"（延迟导入、并行初始化）
- Phase 4 解决"加载多"（不需要的模块根本不加载）
- 两者互补，共同实现轻量启动

#### 涉及文件

- `config/modules.yaml`（新建）
- `backend/tars/main.py`（条件注册路由）
- `backend/tars/modules/__init__.py`（新建，模块加载器）
- `frontend/src/api/index.ts`（获取模块状态）
- `frontend/src/components/layout/Sidebar.vue`（动态菜单）

---

### 6.2 Skill Curator 简化版

#### 目标

技能使用统计 + 手动状态管理。不做自动状态流转。

#### 数据模型

```sql
CREATE TABLE skill_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    invoked_at TEXT NOT NULL,
    trigger_source TEXT,      -- "router" | "manual" | "command"
    success INTEGER DEFAULT 1,
    duration_ms INTEGER
);

CREATE INDEX idx_skill_usage_skill ON skill_usage(skill_id, invoked_at);
CREATE INDEX idx_skill_usage_tenant ON skill_usage(tenant_id, invoked_at);
```

#### 技能状态

| 状态 | 含义 | 行为 |
|------|------|------|
| active | 正常使用 | 参与 SkillRouter 打分 |
| archived | 归档 | 不参与 SkillRouter，搜索可见，可手动重新激活 |

状态由管理员手动设置，不做自动流转。

#### API

```
GET  /api/skills/stats                    — 所有技能使用统计（调用次数、最后使用、成功率）
GET  /api/skills/{id}/stats               — 单个技能详细统计
PUT  /api/skills/{id}/archive             — 归档技能
PUT  /api/skills/{id}/activate            — 重新激活
```

#### 前端展示

- 技能管理页面新增"统计"列：调用次数、最后使用时间
- 状态标签：🟢 活跃 / 📦 归档
- 归档操作：确认弹窗 → 调用 API

#### 涉及文件

- `backend/tars/skills/curator.py`（新建）
- `backend/tars/database/base.py`（新增 skill_usage 表）
- `backend/tars/skills/router.py`（跳过 archived 技能）
- `backend/tars/api/skills.py`（新增统计 + 归档 API）
- `frontend/src/views/ToolsView.vue`（展示统计）

---

### 6.3 集成测试 + 文档

#### 测试策略

| 模块 | 测试类型 | 覆盖重点 | 预计用例数 |
|------|---------|---------|-----------|
| 脱敏引擎 | 单元测试 | 各模式检测准确率、白名单、边界情况 | 15+ |
| 权限隔离 | 集成测试 | 跨 tenant 访问拒绝、workspace 沙箱逃逸 | 10+ |
| 记忆权限 | 集成测试 | scope 隔离、admin 越权、shared 可见性 | 12+ |
| 审计日志 | 集成测试 | 全链路记录、脱敏存储、查询过滤 | 8+ |
| 注入防护 | 单元测试 | 各攻击模式检测、误杀率 | 10+ |
| 连接复用 | 压力测试 | 10 并发用户 × 连续对话，连接数稳定 | 5+ |
| 并发限流 | 压力测试 | 超限排队、公平调度、超时处理 | 8+ |
| Provider 插件 | 单元测试 | 接口一致性、配置加载、热切换 | 10+ |
| Prompt Cache | 单元测试 | 命中/失效/TTL、并发安全 | 8+ |
| 模块化启动 | 冒烟测试 | 禁用模块后启动正常、API 404 | 5+ |

#### 文档产出

| 文档 | 内容 |
|------|------|
| `docs/SECURITY_GUIDE.md` | 安全配置指南（脱敏规则、权限配置、注入防护） |
| `docs/PROVIDER_PLUGIN_GUIDE.md` | 自定义 Provider 开发指南（接口规范、示例） |
| `docs/DEPLOYMENT_GUIDE.md` | 内网部署最佳实践（modules.yaml、concurrency.yaml、Docker） |
| `docs/MEMORY_PERMISSION_GUIDE.md` | 记忆权限说明（scope、共享记忆、admin 管理） |
| `CHANGELOG.md` | v4.0.0 完整变更日志 |

---

## 七、实施路线图

### 总览

```
Week 1-3:  Phase 1（安全加固）+ Phase 2（性能优化）并行
Week 4-5:  Phase 3（Provider 插件化）
Week 6:    Phase 4（平台收尾 + 集成测试）
Week 7:    文档 + 回归测试 + 发布
```

### 详细排期

#### Phase 1: Security Hardening（Week 1-3）

| 周 | 任务 | 产出 |
|----|------|------|
| W1 | 脱敏引擎 + 模式库 | sanitizer.py + patterns.py + 15 个测试 |
| W1 | 审计日志表 + 记录中间件 | audit.py + API |
| W2 | 权限隔离增强（工具权限映射 + workspace 限制） | permission 扩展 + 10 个测试 |
| W2 | 记忆权限管理（scope 字段 + 权限检查器） | memory_permission.py + 12 个测试 |
| W3 | 提示词注入防护 | injection_guard.py + 10 个测试 |
| W3 | Admin 记忆管理 API + 共享记忆 | admin.py API |

#### Phase 2: Performance（Week 1-3，与 Phase 1 并行）

| 周 | 任务 | 产出 |
|----|------|------|
| W1 | 启动优化（延迟导入 + 并行初始化） | lazy.py + main.py 重排 |
| W2 | LLM 连接复用池 | connection_pool.py |
| W2 | Prompt Cache | prompt_cache.py + 失效机制 |
| W3 | 并发限流 + 公平调度 | limiter.py + 配置 + 前端排队提示 |
| W3 | 压力测试 | 10 并发场景验证 |

#### Phase 3: Provider Plugin Architecture（Week 4-5）

| 周 | 任务 | 产出 |
|----|------|------|
| W4 | ProviderBase 抽象 + Registry | base.py + registry.py |
| W4 | OpenAI Compatible 统一层 | openai_compat.py（合并 custom + openrouter） |
| W5 | Ollama Provider 迁移 + 配置化 | plugins/ollama.py + providers.yaml |
| W5 | 热切换 + 前端适配 + 迁移脚本 | ModelsView 改造 |

#### Phase 4: Platform Polish（Week 6）

| 周 | 任务 | 产出 |
|----|------|------|
| W6 | 模块化启动 | modules.yaml + 条件路由注册 |
| W6 | Skill Curator 简化版 | curator.py + 统计 API |
| W6 | 集成测试补全 | 全模块测试通过 |

#### 收尾（Week 7）

| 周 | 任务 | 产出 |
|----|------|------|
| W7 | 文档编写 | 4 份指南文档 |
| W7 | 回归测试（现有功能不退化） | 全量测试通过 |
| W7 | CHANGELOG + README 更新 + 打 tag | v4.0.0 发布 |

---

## 八、成功标准

### 安全指标

- [ ] 敏感信息脱敏覆盖率 > 95%（已知模式）
- [ ] 跨 tenant 数据访问测试全部拒绝
- [ ] 提示词注入检测率 > 80%，误杀率 < 5%
- [ ] 审计日志覆盖所有工具调用和关键操作
- [ ] 记忆权限隔离测试全部通过

### 性能指标

- [ ] 冷启动时间 < 3 秒（当前预估 8-10 秒）
- [ ] 二次启动时间 < 1.5 秒（配置缓存命中）
- [ ] 10 并发用户场景下 LLM 调用延迟无退化
- [ ] Prompt Cache 命中率 > 70%（连续对话场景）
- [ ] 连接池稳定运行 24h 无泄漏

### 可扩展性指标

- [ ] 新增 Provider 只需一个 .py 文件 + providers.yaml 配置
- [ ] 禁用模块后启动正常，API 返回 404
- [ ] 现有功能回归测试 100% 通过
- [ ] 向后兼容：旧配置自动迁移无需手动操作

### 用户体验指标

- [ ] 排队时有明确状态反馈
- [ ] 权限拒绝时有清晰提示（而非静默失败）
- [ ] 记忆管理页面正确展示 scope 和权限状态

---

## 九、风险与应对

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| Provider 重构影响现有配置 | 高 | 中 | 向后兼容导出 + 自动迁移脚本 + 回滚方案 |
| 脱敏引擎误杀正常内容 | 中 | 中 | 白名单机制 + 可配置脱敏级别 + 充分测试 |
| 连接池在长时间运行后泄漏 | 高 | 低 | 健康检查 + 定时回收 + 监控告警 |
| 并发限流影响用户体验 | 中 | 中 | 合理默认值 + 可配置 + 排队状态反馈 |
| Phase 1/2 并行开发冲突 | 低 | 中 | 模块边界清晰，security/ 和 cache/ 独立目录 |
| 记忆 scope 迁移影响现有数据 | 中 | 低 | 默认 scope=private，不影响现有行为 |

---

## 十、不做的事（明确排除，留给 v4.1+）

| 功能 | 推迟理由 | 可能的 v4.1 时间点 |
|------|---------|------------------|
| PyPI 发布 | 内网部署不需要 | 如果有外部用户需求再做 |
| TARS Proxy（OpenAI 兼容代理） | 非核心功能 | v4.1 作为可选模块 |
| 多智能体 Kanban | 探索性太强，ROI 不明确 | v4.2 评估 |
| Checkpoints 状态持久化 | 现有 PDCA paused 恢复够用 | 如果用户反馈崩溃恢复不足再做 |
| 技能架构重构 | 当前架构完整，不需要动 | 技能数量超过 50 个时再评估 |
| Goal 持久目标机制 | 当前 PDCA + 记忆系统覆盖 | v4.2 评估 |
| 自动 Curator 状态流转 | 内网技能少，手动管理够用 | 技能数量增长后再自动化 |

---

## 十一、技术决策记录

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| 脱敏实现方式 | 正则 vs LLM | 正则 | 不增加 LLM 调用开销，延迟可控 |
| 权限模型 | RBAC vs ABAC | RBAC（角色） | 内网场景用户数有限，RBAC 够用且简单 |
| 连接池实现 | 自建 vs httpx 内置 | httpx 内置 AsyncClient | httpx 已有连接池能力，配置 limits 即可 |
| Provider 插件发现 | 约定文件 vs 装饰器注册 | 约定文件（`__provider_class__`） | 简单直接，不需要额外框架 |
| Prompt Cache 存储 | Redis vs 内存 dict | 内存 dict | 单机部署，不引入额外依赖 |
| 并发控制 | asyncio.Semaphore vs 外部队列 | asyncio.Semaphore | 单进程架构，不需要分布式队列 |
| 记忆 scope | 多级（private/team/org/public） vs 二级 | 二级（private/shared） | YAGNI，内网场景二级够用 |
