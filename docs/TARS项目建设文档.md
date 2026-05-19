# TARS AI Agent 项目建设文档

## 一、项目概述

**TARS** 是一个高度自主、可配置的 AI Agent 应用，灵感来自电影《星际穿越》中的机器人 TARS。项目旨在构建一个具有人格特征、记忆能力和工具执行能力的智能助手系统。

### 核心特性

| 特性 | 说明 |
|------|------|
| 🎭 **可调人格** | honesty/humor/initiative/empathy 等 10 项参数实时调节 |
| 🧠 **三层记忆 V3** | Core Memory（4 块固定区块，支持 forget）+ Archival Memory（语义+关键词检索 + Ebbinghaus 衰减）+ 遗忘机制（重要性衰减 + 过期清理） |
| 🔌 **工具系统** | 统一 ToolRegistry + ToolDispatcher，支持原生 Function Calling + Prompt Fallback |
| ⚡ **技能插件** | PluginSkill（Python 代码插件）+ PromptSkill（Prompt 模板）+ skill.yaml 标准化格式 |
| 📦 **SkillHub 市场** | 本地 bundled 技能目录 + GitHub，支持 SKILL.md 一键安装（v4.0.5） |
| 📤 **多模态** | 支持图片和文档上传，多模态模型直接理解图片，非多模态模型自动 OCR 降级 |
| 🎨 **Markdown 渲染** | marked.js + highlight.js 代码语法高亮 + 代码块一键复制 |
| ⌨️ **键盘快捷键** | Ctrl+Enter 发送 / Ctrl+/ 命令面板 / Ctrl+L 新会话 |

---

## 二、建设思路

### 设计理念

TARS 的设计融合了多个优秀项目的思想：

- **OpenClaw** - 五层架构和工作区文件系统
- **Hermes Agent** - 工具注册表和技能生态系统
- **Letta** - 三层记忆架构（Core + Archival + Reflector）

### 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: Channels（通道层）                                      │
│   WebSocket / Telegram / 飞书 / Webhook                          │
├─────────────────────────────────────────────────────────────────┤
│ Layer 2: Gateway（网关层）                                       │
│   身份核验 / 速率限制 / 安全策略 / Session 路由                   │
├─────────────────────────────────────────────────────────────────┤
│ Layer 3: Agent（智能体层）                                       │
│   Agent Loop / 工作区 / 记忆系统 V3 / 子代理                     │
├─────────────────────────────────────────────────────────────────┤
│ Layer 4: Model（模型层）                                         │
│   OpenRouter / Anthropic / OpenAI / Ollama                      │
├─────────────────────────────────────────────────────────────────┤
│ Layer 5: Execution（执行层）                                     │
│   terminal / file / browser / web / delegate / cronjob / memory │
└─────────────────────────────────────────────────────────────────┘
```

### 核心模块设计

#### 1. 记忆系统 V3（Letta 混合模式）

| 模块 | 职责 |
|------|------|
| **core_memory.py** | 4 块固定区块的读写，支持 append/replace/forget + 自动去重 + 行数上限 |
| **archival.py** | 长期记忆存储，支持 CRUD、source 标签、importance 评分、访问统计 |
| **search.py** | 基于 embedding 的语义检索 + FTS5 关键词 + CJK LIKE 降级 |
| **decay.py** | Ebbinghaus 衰减算法 + 重要性自然衰减（每日 -0.01） |
| **reflector.py** | 每轮对话后异步运行：更新 core memory + 提取 archival + forget 清理过时内容 |
| **manager.py** | Facade 层，向 Agent Loop 暴露读写入口 + 遗忘清理 |
| **database/base.py** | `decay_importance()` 自然衰减 + `cleanup_old_memories()` 过期删除 + `forget_core_line()` 按行删除 |

#### 2. 工具系统

- **ToolRegistry**: 唯一注册中心，一次注册全局可用
- **ToolDispatcher**: 支持 LLM 原生 Function Calling + Prompt Fallback
- **WorkspaceSandbox**: 路径安全隔离
- **PluginLoader**: Python 插件动态加载

#### 3. 技能系统

- **PluginSkill**: Python 代码插件，动态加载注册为 Tool
- **PromptSkill**: Prompt 模板，注入 LLM 上下文
- **skill.yaml**: 标准化技能包格式

#### 4. 斜杠命令系统（v2.1.0）

- **CommandParser**: 解析 `/xxx args` 语法
- **CommandRegistry**: 注册中心，7 个内置命令
- **Command.execute()**: 返回 `prompt_injection` + `frontend_message` + `action`
- 前端 `/` 按钮下拉菜单

#### 5. Python 沙箱执行（v2.1.0）

- **python_exec**: 子进程执行 Python 代码，返回 stdout/stderr/exit_code
- 使用 `sys.executable` 确保与 venv 一致
- 支持 pandas / openpyxl / Pillow / pypdf / python-docx

---

## 三、建设总结

### 项目结构

```
TARS/
├── backend/                    # 后端（Python + FastAPI）
│   ├── tars/
│   │   ├── agent/              # Agent 层
│   │   ├── tools/              # 工具层
│   │   ├── memory/             # 记忆系统 V3
│   │   ├── orchestration/      # 任务编排
│   │   ├── skills/             # 技能层
│   │   ├── skillhub/           # SkillHub 市场
│   │   ├── files/              # 文件上传
│   │   ├── models/             # LLM Provider
│   │   ├── database/           # 数据库
│   │   ├── workspace/          # 工作空间
│   │   ├── channels/           # 通信通道
│   │   ├── api/                # API 路由
│   │   └── main.py             # FastAPI 入口
│   ├── tests/                  # 测试用例（75+ cases）
│   ├── skills/                 # 本地 Skill 包目录
│   └── uploads/                # 文件上传目录
├── frontend/                   # 前端（Vue 3 + TypeScript）
│   └── src/
│       ├── views/              # 页面（ChatView/ToolsView/SettingsView）
│       ├── components/         # 组件
│       └── api/                # API 层
├── skills/                     # 技能市场技能包
└── docs/                       # 项目文档
```

### 实施进度

| 阶段 | 名称 | 状态 | 描述 |
|------|------|------|------|
| Phase 1 | 项目骨架 | ✅ | Git 仓库、项目结构、WebSocket 连接 |
| Phase 2 | 对话功能 | ✅ | Agent Loop、LLM Provider、会话管理 |
| Phase 3 | Gateway | ✅ | 身份验证、速率限制、安全策略 |
| Phase 4 | SOUL 人格 | ✅ | 工作区文件解析、人格参数可视化 |
| Phase 5 | 记忆系统 | ✅ | 双层存储、自动提取、全文检索 |
| Phase 6 | 工具系统 | ✅ | 工具注册表、核心工具实现 |
| Phase 7 | 技能系统 | ✅ | 技能加载器、技能市场 |
| Phase 8 | Web 完善 | ✅ | PWA、深色模式、响应式设计 |
| Phase 9 | 桌面化 | ✅ | Tauri 包装、系统托盘 |

### 技术栈

| 分类 | 技术 | 版本 |
|------|------|------|
| 后端框架 | FastAPI | >=0.109.0 |
| 语言 | Python | 3.11+ |
| 数据库 | SQLite + FTS5 | - |
| 异步 | asyncio | - |
| 前端框架 | Vue 3 | - |
| 语言 | TypeScript | - |
| 构建工具 | Vite | - |
| 样式 | TailwindCSS | - |
| 状态管理 | Pinia | - |
| LLM 支持 | OpenRouter/Anthropic/OpenAI/Ollama | - |

---

## 四、部署方案

### 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.11+ |
| Node.js | 18+ |
| 内存 | 2GB+（推荐 4GB+） |
| 存储 | 500MB+ |
| 操作系统 | macOS / Linux / Windows (WSL2) |

### 本地开发部署

#### 1. 克隆代码

```bash
git clone <repo-url>
cd TARS
```

#### 2. 后端设置

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 .\venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API Key
```

#### 3. 前端设置

```bash
cd ../frontend

# 安装依赖
npm install

# 开发模式启动
npm run dev
```

#### 4. 启动服务

```bash
# 后端（在 backend/ 目录下）
source venv/bin/activate
pip install pandas openpyxl Pillow sentence-transformers
venv/bin/python3 -m uvicorn tars.main:app --host 0.0.0.0 --port 8000

# 前端（在 frontend/ 目录下）
npm run dev
```

访问 `http://localhost:5173` 即可使用。

### 配置说明

#### 环境变量

```bash
# .env
OPENROUTER_API_KEY=sk-or-...
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

TARS_DATA_DIR=~/.tars
TARS_HOST=0.0.0.0
TARS_PORT=8000
```

#### 配置文件 `~/.tars/config.yaml`

```yaml
model:
  provider: openrouter
  model: anthropic/claude-sonnet-4
  context_length: 128000
  temperature: 0.7

providers:
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
    base_url: "https://openrouter.ai/api/v1"
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    base_url: "https://api.anthropic.com"
  openai:
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://api.openai.com/v1"
  ollama:
    base_url: "http://localhost:11434"

security:
  dangerous_commands:
    - rm -rf
    - mkfs
    - dd if=
  allowed_paths:
    - ~/.tars
    - ~/projects
  blocked_paths:
    - /etc
    - /var
    - /root

rate_limit:
  requests_per_minute: 30
  max_tokens_per_request: 8000
```

### Docker 部署

#### docker-compose.yml

```yaml
version: "3.8"

services:
  backend:
    build:
      context: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ~/.tars:/root/.tars
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}

  frontend:
    build:
      context: ./frontend
    ports:
      - "5173:5173"
    depends_on:
      - backend
```

#### 启动

```bash
docker-compose up -d
```

### 桌面端部署（Tauri）

```bash
cd frontend
npm run tauri dev    # 开发模式
npm run tauri build  # 打包发布
```

### 备份策略

```bash
# 备份数据目录
tar -czf tars-backup-$(date +%Y%m%d).tar.gz ~/.tars
```

---

## 五、API 接口总览

### 会话管理 `/api/sessions/`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/sessions/` | 列出会话 |
| POST | `/api/sessions/` | 创建新会话 |
| GET | `/api/sessions/{id}/messages` | 获取会话历史 |
| DELETE | `/api/sessions/{id}` | 删除会话 |
| PATCH | `/api/sessions/{id}` | 更新会话标题 |

### 工具管理 `/api/tools/`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/tools/` | 列出所有工具 |
| GET | `/api/tools/{id}` | 工具详情 |
| PUT | `/api/tools/{id}/status` | 启用/禁用 |
| POST | `/api/tools/execute` | 手动执行 |

### 技能管理 `/api/skills/`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/skills/` | 列出已安装技能 |
| POST | `/api/skills/create-prompt` | 创建 PromptSkill |
| PUT | `/api/skills/{id}/enable` | 启用 |
| DELETE | `/api/skills/{id}` | 卸载 |

### SkillHub `/api/skillhub/`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/skillhub/search?q=xxx` | 搜索技能 |
| POST | `/api/skillhub/install` | 安装 |
| POST | `/api/skillhub/uninstall` | 卸载 |

### 文件上传 `/api/files/`

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/files/upload` | 上传文件 |
| GET | `/api/files/{file_id}` | 获取文件信息 |
| DELETE | `/api/files/{file_id}` | 删除文件 |

### WebSocket

| 路径 | 描述 |
|------|------|
| `/ws` | 聊天通信 |

---

## 六、测试运行

```bash
cd backend
./venv/bin/python3 -m pytest tests/ -v
# 75 tests passed（工具/技能 39 + 文件上传 18 + 默认技能 18）
```

---

*文档版本: v2.3*  
*创建日期: 2026-05-06*  
*更新日期: 2026-05-09*