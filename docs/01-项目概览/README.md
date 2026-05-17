# TARS — 通用本地 AI Agent 平台

## 项目简介

TARS 是一个面向内网多用户部署的 AI Agent 平台，支持本地模型（Ollama）和云端 API（DeepSeek、阿里通义等）。用户通过技能/插件适配垂直场景，平台提供安全隔离、记忆管理、工具调度等基础能力。

**当前版本: v4.0.0 "Hardened Base"**

## 核心特性

### 智能交互
- 🎭 **可调人格** — honesty / humor / initiative / empathy 四维参数实时调节
- 🧠 **三层记忆系统** — Core Memory（persona + user_profile + project_context + working_principles）+ Archival Memory（embedding 语义检索 + Ebbinghaus 衰减）+ Reflector 异步反思沉淀
- ⚡ **流式响应** — WebSocket 实时推送，打字机效果

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

| 文档 | 说明 |
|------|------|
| [系统架构](../02-技术方案/architecture/system-overview.md) | 整体架构设计 |
| [前端设计 v4.0.0](../02-技术方案/v4.0.0-frontend-design.md) | v4 前端适配方案 |
| [WebSocket 协议](../02-技术方案/api/websocket-protocol.md) | 前后端通信协议 |
| [部署指南](../04-运维文档/deployment.md) | 内网部署说明 |
| [Changelog](./changelog.md) | 版本变更记录 |

---

*文档版本: v4.0.0*
*更新日期: 2026-05-17*
