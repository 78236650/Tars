# TARS — 通用本地 AI Agent 平台

## 项目简介

TARS 是一个面向内网多用户部署的 AI Agent 平台，支持本地模型（Ollama）和云端 API（DeepSeek、阿里通义等）。用户通过技能/插件适配垂直场景，平台提供安全隔离、记忆管理、工具调度等基础能力。

**当前版本: v4.3.2** — Superpowers + **LLM Wiki / RAG 双通路**（详见 [VERSION.md](./VERSION.md)）  
**上一版本: v4.3.1**（会议 ASR、知识库深度入库、BI、INS-2.1）  
**稳定基线: v4.1.2**（生产/内网部署参考）  
**Git 分支**: `v4.3.2`（与产品版本一致，见 [VERSION.md](./VERSION.md)）

### 平台版本 vs InsightForge 能力版本（双轨，方案 A）

| TARS 平台 | InsightForge（`GET /api/insight/version`） | 说明 |
|-----------|---------------------------------------------|------|
| **v4.3.2**（当前） | **INS-2.1.0** | Superpowers + Wiki/RAG 双通路、`read_wiki` / `write_wiki` |
| v4.3.1 | INS-2.1.0 | 建档性能（batch stats、增量 reuse、SQL 超时） |
| v4.2.0 | INS-2.0.0 | Data Copilot 与 KnowledgeBridge 联动 |
| — | INS-1.0.0 | 早期 Profile 流水线（历史 tag `insight-v1.0.0`） |

- 平台号：`backend/tars/main.py` → OpenAPI **4.3.2**
- 能力号：`backend/tars/insight/version.py` → **INS-2.1.0**（勿与 `4.3.2` 混用同一字符串）
- Git 能力 tag 建议：`insight-v2.1.0`（与 `insight-v2.0.0` 并列，不替代平台分支名）

## 核心特性

### 智能交互
- 🎭 **可调人格** — honesty / humor / initiative / empathy 四维参数实时调节
- 🧠 **三层记忆系统** — Core Memory（persona + user_profile + project_context + working_principles）+ Archival Memory（embedding 语义检索 + Ebbinghaus 衰减）+ Reflector 异步反思沉淀
- ⚡ **流式响应** — WebSocket 实时推送，打字机效果
- 📚 **知识库主动检索** — Agent 每轮对话前自动检索相关知识并注入上下文（v4.0.5）

### SkillHub 技能生态（v4.0.5）
- 📦 **本地 bundled 技能** — 10 个精选技能一键安装（PDF、GitHub、Excel 等）
- ⚡ **装了就能用** — 安装后自动注册，Agent 按消息上下文注入技能指令
- 🏷️ **精选目录** — featured 筛选 + 安装用法与示例 prompt 展示

### Admin 管理台（v4.0.5）
- 👥 **用户管理** — 编辑用户名、邮箱、角色、密码
- 🎭 **角色模板** — 分配角色模板与权限查看
- 📋 **审计日志** — 用户/会话/技能/工具事件追踪

### 安全加固（v4.0.0）
- 🔒 **敏感信息脱敏** — 自动检测并掩码 API Key、手机号、邮箱、银行卡、私钥等
- 🛡️ **提示词注入防护** — 规则引擎检测角色覆盖、delimiter 注入、jailbreak 等攻击
- 📋 **审计日志** — 全量记录工具调用、权限拒绝、模型调用等操作
- 🔐 **记忆权限隔离** — private/shared 双作用域，跨租户隔离 + 共享记忆
- 🎫 **角色工具权限** — YAML 配置 admin/user/guest 可用工具白名单

### 性能优化（v4.0.0）
- 🚀 **延迟导入** — 重型依赖首次使用时加载，冷启动加速
- 🔗 **连接复用池** — httpx AsyncClient 共享，多用户并发延迟降低 30-50%
- 💾 **Prompt Cache** — System Prompt 静态部分 TTL 缓存，命中时 <5ms
- ⚖️ **并发限流** — per-user 公平调度 + 全局 Semaphore，防止单用户独占

### Provider 插件化（v4.0.0）
- 🔌 **统一接口** — ProviderBase ABC，新增 Provider 只需一个 .py 文件
- 📦 **内置插件** — Ollama + OpenAI Compatible（覆盖 DeepSeek、通义、OpenRouter 等）
- ⚙️ **配置驱动** — `providers.yaml` 声明式配置，支持 `${ENV_VAR}` 展开
- 🔄 **热切换** — 运行时切换 Provider/模型，无需重启

### 平台能力
- 🛠️ **14 个内置工具** — weather、web_search、web_fetch、file、file_write、shell、command、python_exec、memory、cronjob、knowledge_search、meeting_recognizer、network、process
- 📚 **10 个技能** — bi_analytics、calculator、code_assistant、deploy、meeting_notes、planner、release_notes、run_tests、summarizer、translator
- 📊 **模块化启动** — modules.yaml 控制可选模块（BI、会议、知识库、SkillHub）按需加载
- 📈 **技能统计** — Curator 记录调用次数/成功率，支持归档管理

### v4.3.2（Superpowers + Wiki）

- 🎯 **Skill 自动路由** — `triggers` / `skip_when` + embedding
- 📋 **Plan 审批门控** — WebSocket 审批 + checkpoint + `PlanReviewDialog`
- ✅ **Verification Gate** — skill `verify` 命令门控
- 📖 **LLM Wiki** — 与 RAG 并存；`read_wiki` / `write_wiki`；知识库 Wiki Tab
- 📖 升级：[UPGRADE_GUIDE_v4.3.2.md](../UPGRADE_GUIDE_v4.3.2.md) · Wiki：[guides/wiki-user.md](../guides/wiki-user.md) · Skill：[SKILL_AUTHORING.md](../SKILL_AUTHORING.md)

## 技术栈

### 后端
| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI + WebSocket |
| 语言 | Python 3.11+ |
| 数据库 | SQLite + FTS5 全文检索 |
| 向量检索 | ChromaDB + bge-small-zh-v1.5 |
| 异步 | asyncio |
| HTTP 客户端 | httpx（连接池复用） |

### 前端
| 组件 | 技术 |
|------|------|
| UI 框架 | Vue 3 (Composition API) |
| 路由 | Vue Router 4 |
| 样式 | Tailwind CSS 3 |
| 构建 | Vite 5 |
| 语言 | TypeScript |

### 模型支持
| Provider | 说明 |
|----------|------|
| Ollama | 本地模型（qwen3、llama3、deepseek 等） |
| OpenAI Compatible | 通用协议（DeepSeek、通义千问、Kimi、vLLM 等） |

## 项目结构

```
TARS/
├── backend/
│   ├── tars/
│   │   ├── agent/          # Agent 核心（消息处理、工具调度）
│   │   ├── api/            # REST API 路由
│   │   ├── cache/          # Prompt Cache
│   │   ├── concurrency/    # 并发限流
│   │   ├── database/       # SQLite 数据层
│   │   ├── memory/         # 三层记忆系统
│   │   ├── models/         # Provider 插件架构
│   │   │   └── plugins/    # 内置 Provider（ollama、openai_compat）
│   │   ├── modules/        # 模块化启动
│   │   ├── security/       # 安全加固（脱敏、审计、注入防护、权限）
│   │   ├── skills/         # 技能系统 + Curator
│   │   └── tools/          # 工具注册与调度
│   ├── config/             # YAML 配置（providers、modules、concurrency、tool_permissions）
│   └── tests/              # 157+ 单元/集成测试
├── frontend/               # Vue 3 前端
├── skills/                 # 本地技能包目录
├── scripts/                # 运维脚本
└── docs/                   # 项目文档
```

## 快速开始

```bash
# 1. 克隆
git clone <repo-url> && cd TARS

# 2. 后端
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 编辑配置

# 3. 前端
cd ../frontend
npm install

# 4. 启动
# 后端
cd ../backend && .venv/bin/python -m uvicorn tars.main:app --host 0.0.0.0 --port 8000
# 前端
cd ../frontend && npm run dev
```

## 配置文件

| 文件 | 说明 |
|------|------|
| `backend/.env` | 环境变量（API Key 等） |
| `backend/config/providers.yaml` | LLM Provider 配置 |
| `backend/config/modules.yaml` | 可选模块启用/禁用 |
| `backend/config/concurrency.yaml` | 并发限流参数 |
| `backend/config/tool_permissions.yaml` | 角色工具权限 |

## 文档导航

### 我是…

| 角色 | 先看 |
|------|------|
| 产品 / 运维 | [VERSION.md](./VERSION.md) → [v4.3.2 发布说明](./v4.3.2-release-notes.md) → [部署](../04-运维文档/deployment.md) |
| 从 4.3.1 升级 | [UPGRADE_GUIDE_v4.3.2.md](../UPGRADE_GUIDE_v4.3.2.md) |
| 用 Wiki / 知识库 | [guides/wiki-user.md](../guides/wiki-user.md) |
| 写 Skill | [SKILL_AUTHORING.md](../SKILL_AUTHORING.md) |
| 查设计稿 | [superpowers/README.md](../superpowers/README.md) |

### 版本与变更

| 文档 | 说明 |
|------|------|
| [VERSION.md](./VERSION.md) | **版本真相源**（平台 / INS / Git 分支） |
| [changelog.md](./changelog.md) | 全量变更记录 |
| [v4.3.2-release-notes.md](./v4.3.2-release-notes.md) | 当前版本 |
| [v4.3.1-release-notes.md](./v4.3.1-release-notes.md) | 上一 patch |
| [roadmap.md](../03-实施计划/roadmap.md) | 里程碑（已完成项链到 changelog） |

### 架构与协议

| 文档 | 说明 |
|------|------|
| [系统架构](../02-技术方案/architecture/system-overview.md) | 整体架构 |
| [WebSocket 协议](../02-技术方案/api/websocket-protocol.md) | 前后端通信 |
| [guides/](../guides/README.md) | 用户与运维指南索引 |

---

*文档版本: v4.3.2 · 更新日期: 2026-05-26*
