# TARS AI Agent v2.1.0

一个完整的 AI 助手应用，支持多用户权限管理、专业子代理委派、可配置人格参数、工具调用（Function Calling）、技能插件系统、文件上传与多模态理解。

## 项目结构

```
TARS/
├── backend/                        # 后端（Python + FastAPI）
│   ├── tars/
│   │   ├── agent/                  # Agent 层
│   │   │   ├── agent.py            # AgentV2（ToolDispatcher + 多模态 + 记忆反思）
│   │   │   ├── subagent_manager.py # 子代理管理器
│   │   │   └── subagents/          # 5 个专业子代理
│   │   ├── tools/                  # 工具层
│   │   │   ├── base.py             # BaseTool + ToolResult
│   │   │   ├── registry.py         # ToolRegistry（唯一注册中心）
│   │   │   ├── dispatcher.py       # ToolDispatcher（Function Calling + Prompt Fallback）
│   │   │   ├── sandbox.py          # WorkspaceSandbox（路径安全）
│   │   │   ├── plugin_loader.py    # Python 插件动态加载
│   │   │   └── builtin/            # 内置工具
│   │   │       ├── weather.py      # 天气查询
│   │   │       ├── file.py         # 文件读取
│   │   │       ├── file_write.py   # 文件写入（write/append/insert）
│   │   │       ├── shell.py        # Shell 命令（黑名单 + 确认）
│   │   │       ├── process.py      # 进程管理
│   │   │       ├── network.py      # 网络诊断
│   │   │       ├── memory.py       # 记忆管理
│   │   │       ├── cronjob.py      # 定时任务
│   │   │       ├── web_search.py   # 网页搜索
│   │   │       ├── web_fetch.py    # 网页抓取
│   │   │       └── python_exec.py  # Python 沙箱执行（★v2.1.0）
│   │   ├── commands/               # 斜杠命令系统（★v2.1.0）
│   │   │   ├── base.py             # Command + CommandResult
│   │   │   ├── registry.py         # CommandRegistry 注册中心
│   │   │   ├── parser.py           # CommandParser（/xxx args 解析）
│   │   │   └── builtin.py          # 7 个内置命令
│   │   ├── memory/                 # 记忆系统 V3（Letta 混合模式）
│   │   │   ├── core_memory.py      # 4 块 Core Memory + 编辑工具
│   │   │   ├── archival.py         # Archival Memory（写入 + 去重）
│   │   │   ├── reflector.py        # 后处理反思 LLM
│   │   │   ├── decay.py            # Ebbinghaus 衰减评分
│   │   │   ├── search.py           # 混合搜索（语义 + FTS + 衰减）
│   │   │   ├── manager.py          # MemoryManager 整合层
│   │   │   ├── embeddings.py       # 嵌入向量 Provider
│   │   │   ├── deduplicator.py     # 记忆去重
│   │   │   └── extractor.py        # LLM/正则提取器
│   │   ├── orchestration/          # 任务编排
│   │   │   ├── planner.py          # TaskPlannerTool
│   │   │   ├── executor.py         # TaskExecutor（多步执行 + 重试）
│   │   │   └── models.py           # TaskPlan / TaskStep
│   │   ├── skills/                 # 技能层
│   │   │   ├── base.py             # Skill, PluginSkill, PromptSkill
│   │   │   ├── registry.py         # SkillRegistry
│   │   │   ├── loader.py           # skill.yaml 加载器
│   │   │   └── executor.py         # PromptSkill 注入
│   │   ├── skillhub/               # SkillHub 市场
│   │   │   ├── client.py           # GitHub API 客户端
│   │   │   ├── installer.py        # 安装/卸载/更新
│   │   │   └── models.py           # 数据模型
│   │   ├── files/                  # 文件上传
│   │   │   ├── storage.py          # 文件存储
│   │   │   ├── parser.py           # 文件解析（PDF/Word/Excel/OCR）
│   │   │   └── models.py           # FileRecord + ParsedContent
│   │   ├── models/                 # LLM Provider 层
│   │   │   ├── ollama.py           # Ollama（Function Calling + 多模态）
│   │   │   ├── openrouter.py       # OpenRouter
│   │   │   └── custom.py           # 自定义模型
│   │   ├── database/               # 数据库层（SQLite + FTS5）
│   │   ├── workspace/              # 工作空间（人格系统）
│   │   ├── channels/               # 通信通道（WebSocket）
│   │   ├── api/                    # API 路由
│   │   │   ├── tools.py            # /api/tools/
│   │   │   ├── skills.py           # /api/skills/
│   │   │   ├── skillhub.py         # /api/skillhub/
│   │   │   └── files.py            # /api/files/
│   │   └── main.py                 # FastAPI 应用入口
│   ├── tests/
│   │   ├── test_tools_skills.py    # 工具/技能测试（39 cases）
│   │   ├── test_file_upload.py     # 文件上传测试（18 cases）
│   │   ├── test_memory_v3.py       # 记忆 V3 测试（25 cases）
│   │   ├── test_memory_v2.py       # 记忆 V2 兼容测试（24 cases）
│   │   ├── test_os_orchestration.py # OS 工具 + 编排测试（22 cases）
│   │   └── test_default_skills.py  # 默认技能测试（18 cases）
│   └── skills/                     # 本地 Skill 包目录
└── frontend/                       # 前端（Vue 3 + TypeScript）
    └── src/
        ├── views/
        │   ├── ChatView.vue        # 聊天页（含文件上传 + 计划卡片）
        │   ├── ToolsView.vue       # 工具管理（Tab 布局）
        │   └── SettingsView.vue    # 设置页
        ├── components/
        │   ├── chat/
        │   │   ├── ChatPanel.vue   # 聊天面板（工具调用 + 计划可视化）
        │   │   └── PlanCard.vue    # 任务计划执行卡片
        │   └── tools/              # 工具卡片/详情/添加
        ├── stores/
        │   └── wsStore.ts          # WebSocket 全局状态（★v2.1.0）
        ├── api/index.ts            # API 层
        ├── i18n/index.ts           # 国际化（中/英）
        └── types/index.ts          # 类型定义
```

## v2.0.0 新特性

### 工具系统重构
- **统一 ToolRegistry** — 一次注册，全局可用
- **ToolDispatcher** — 支持 LLM 原生 Function Calling（qwen3 等）+ Prompt Fallback（不支持的模型）
- **多轮工具调用** — 单次对话中可连续调用多个工具

### 技能插件系统
- **PluginSkill** — Python 代码插件，动态加载注册为 Tool
- **PromptSkill** — Prompt 模板，注入 LLM 上下文
- **skill.yaml** — 标准化技能包格式

### SkillHub 市场
- 基于 GitHub Releases 的真实技能市场
- 搜索、安装、卸载、更新
- 权限声明 + 安全校验

### 文件上传与多模态
- 支持图片（jpg/png/gif/webp）和文档（txt/md/pdf/docx/xlsx/csv/代码）
- 多模态模型（llava 等）直接理解图片
- 非多模态模型自动 OCR 降级 + 提示切换模型
- HTTP 上传 + WebSocket 引用

### 前端升级
- ToolsView Tab 布局（内置工具 / 已安装技能 / SkillHub 商店）
- ChatPanel 工具调用可视化
- 文件上传 UI（📎 按钮 + 附件预览）
- PlanCard 任务计划执行进度卡片
- 中英双语切换
- 会话列表（Sidebar 内）支持多会话独立历史 + 新建/切换/删除

### OS 工具 + 任务编排
- **file_write** — 文件创建/写入/追加/插入（WorkspaceSandbox 路径安全）
- **shell** — Shell 命令执行（黑名单 + 危险命令确认）
- **process** — 进程管理（list/start/stop/status）
- **network** — 网络诊断（ping/port_check/http_test/dns_lookup）
- **task_planner** — LLM 生成多步执行计划，系统自动按步骤执行
- **TaskExecutor** — 自动重试 + 失败决策（retry/skip/abort）+ 占位符替换

## v2.1.0 新特性

### 斜杠命令系统

在聊天输入框输入 `/` 或点击输入栏左侧紫色 `/` 按钮，弹出命令菜单：

| 命令 | 说明 | 效果 |
|------|------|------|
| `/plan <任务>` | 规划模式 | 注入规划约束到 system prompt，只分析不写代码 |
| `/yolo` | 执行模式 | 注入执行约束，直接动手快速实现 |
| `/brainstorm <主题>` | 头脑风暴 | 发散思维，列举方向+选 top3 |
| `/subagent <code\|writing\|data\|research> <任务>` | 委派子代理 | 任务路由到专业子代理执行 |
| `/skill <技能名>` | 激活技能 | 启用指定 PromptSkill |
| `/clear` | 新对话 | 创建新会话，清空上下文 |
| `/help` | 帮助 | 显示所有命令列表 |

命令系统架构：`CommandParser` 解析 `/xxx args` → `Command.execute()` 返回 `prompt_injection` + `frontend_message` + `action`。

### Python 沙箱执行 (`python_exec`)

Agent 可写 Python 代码并在沙箱子进程中运行，返回 stdout/stderr/exit_code。

```python
# TARS 对话中自动调用的示例
python_exec(code="import pandas as pd\ndf = pd.read_csv('data.csv')\nprint(df.describe())")
```

**已装 Python 包**：`pandas` `opnpyxl` `Pillow` `pypdf` `python-docx`

**适用场景**：读取 CSV/Excel/PDF、数据分析、图片处理、格式转换、快速原型。

### 记忆系统强化

**调出（Recall）：**
- **核心记忆去重** — `CoreMemoryManager.append()` 自动检测重复行，避免同一内容堆积
- **行数上限** — 每个核心记忆区块最多 30 行，超出自动删除最旧行
- **CJK 中文降级搜索** — FTS5 无法切分中文时自动降级为 `LIKE '%关键词%'` 搜索
- **检索调试日志** — `[HybridSearch] query="..." semantic=N keyword=N top=N | 命中预览`

**遗忘（Forgetting）：**
- **重要性自然衰减** — 超过 24h 未访问的 Archival 记忆，importance 每日 -0.01（下限 0.1）
- **过期记忆清理** — 启动时自动删除 `imp < 0.25` 且 15 天未访问的记忆
- **Reflector forget** — 反思器可主动删除过时的 core memory 行（`op: "forget"`）
- **FTS 索引重建** — 删除后自动重建全文索引

### SkillHub 改进

- **本地技能目录** — `GET /api/skillhub/catalog` 返回预置技能列表（无需搜索）
- **安装状态标注** — 目录/搜索结果标注 `installed: true/false`
- **安装后用法说明** — 返回 `usage` 字段告知用户技能如何生效
- **兼容性校验** — 安装前检查 `tars_version_min` + `requires_packages`

### 前端改进

- **WebSocket 持久连接** — `wsStore` Pinia store 全局管理，切换页面不断连
- **Enter 键换行** — 输入框 Enter 自然换行，仅点击 Send 按钮提交
- **命令下拉菜单** — `/` 按钮悬浮弹出 7 个命令，点击自动填入

## 记忆系统 V3（Letta 混合模式）

TARS 采用三层记忆架构：

1. **Core Memory（4 块固定区块）** — 注入 system prompt，支持 append/replace/forget：
   - `persona` Agent 人格定位
   - `user_profile` 用户画像（身份/技术栈/偏好）
   - `project_context` 当前项目上下文
   - `working_principles` 协作准则累积
2. **Archival Memory（长期记忆）** — embedding 语义检索 + FTS5 关键词 + Ebbinghaus 衰减评分
3. **Reflector（反思器）** — 每轮对话后异步更新 core + archival，支持 forget 操作清理过时内容
4. **遗忘机制** — 重要性自然衰减（每日 -0.01）+ 过期自动清理（imp<0.25 & 15天未访问）

Agent 通过 `core_memory_append` / `core_memory_replace` 工具自主编辑核心记忆；反思器作为兜底每轮触发。
Web 工具搜索结果通过反思器自动沉淀为 `source=web` 的 archival 记忆。

详见 [docs/superpowers/specs/2026-05-06-memory-v3-letta-design.md](docs/superpowers/specs/2026-05-06-memory-v3-letta-design.md)

## 快速开始

### 后端启动

```bash
cd backend

# 创建虚拟环境并安装依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pandas openpyxl Pillow sentence-transformers

# 启动服务
venv/bin/python3 -m uvicorn tars.main:app --host 0.0.0.0 --port 8000
```

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

## API 文档

### 会话管理 `/api/sessions/`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/sessions/` | 列出会话（按 updated_at 倒序） |
| POST | `/api/sessions/` | 创建新会话 |
| GET | `/api/sessions/{id}/messages` | 获取会话历史消息 |
| DELETE | `/api/sessions/{id}` | 删除会话 + 关联消息 |
| PATCH | `/api/sessions/{id}` | 更新会话标题 |

### 工具管理 `/api/tools/`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/tools/` | 列出所有工具 |
| GET | `/api/tools/{id}` | 工具详情 |
| PUT | `/api/tools/{id}/status` | 启用/禁用 |
| PUT | `/api/tools/{id}/config` | 更新配置 |
| POST | `/api/tools/execute` | 手动执行（调试） |

### 技能管理 `/api/skills/`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/skills/` | 列出已安装技能 |
| GET | `/api/skills/{id}` | 技能详情 |
| POST | `/api/skills/create-prompt` | 创建 PromptSkill |
| PUT | `/api/skills/{id}/enable` | 启用 |
| PUT | `/api/skills/{id}/disable` | 禁用 |
| DELETE | `/api/skills/{id}` | 卸载 |

### SkillHub `/api/skillhub/`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/skillhub/catalog` | 本地技能目录（★v2.1.0） |
| GET | `/api/skillhub/search?q=xxx` | 搜索技能（本地目录优先） |
| GET | `/api/skillhub/detail/{id}` | 包详情 |
| POST | `/api/skillhub/install` | 安装 |
| POST | `/api/skillhub/uninstall` | 卸载 |
| GET | `/api/skillhub/installed` | 已安装列表 |
| GET | `/api/skillhub/updates` | 检查更新 |

### 文件上传 `/api/files/`

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/files/upload` | 上传文件（multipart/form-data） |
| GET | `/api/files/{file_id}` | 获取文件信息 |
| DELETE | `/api/files/{file_id}` | 删除文件 |

### 其他 API

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/models` | 可用模型列表 |
| POST | `/api/models/switch` | 切换模型 |
| GET/PUT | `/api/personality` | 人格设置 |
| GET/PUT | `/api/subagents` | 子代理配置 |
| GET/POST/DELETE | `/api/users` | 用户管理 |
| GET/POST/DELETE | `/api/cronjobs` | 定时任务 |
| WebSocket | `/ws` | 聊天通信 |

## 技术栈

### 后端
- Python 3.8+
- FastAPI + Uvicorn
- SQLite
- httpx（HTTP 客户端）
- pypdf / python-docx / openpyxl（文档解析）
- Pillow + pytesseract（图片处理 + OCR）

### 前端
- Vue 3 + TypeScript
- TailwindCSS
- Pinia（状态管理）
- Vite（构建）

## 测试

```bash
cd backend
./venv/bin/python3 -m pytest tests/ -v
# 75 tests passed (39 tools/skills + 18 file upload + 18 default skills)
```

## 文档索引

| 文档 | 说明 |
|------|------|
| [SKILLS_GUIDE.md](SKILLS_GUIDE.md) | 技能系统指南（v2.0） |
| [TOOL_CALLING_GUIDE.md](TOOL_CALLING_GUIDE.md) | 工具调用指南（v2.0） |
| [FILE_UPLOAD_GUIDE.md](FILE_UPLOAD_GUIDE.md) | 文件上传与多模态指南（v2.0） |
| [CRONJOB_GUIDE.md](CRONJOB_GUIDE.md) | 定时任务指南 |
| [EVOLUTION_GUIDE.md](EVOLUTION_GUIDE.md) | 自进化系统指南 |
| [DESIGN.md](DESIGN.md) | 初始架构设计（v1.0 归档） |
| [DESIGNV1.md](DESIGNV1.md) | 详细设计方案（v1.0 归档） |

## 版本历史

### v2.1.0（当前）
- 🚀 **Python 沙箱执行** (`python_exec`) — Agent 可写 Python 代码并执行，支持 pandas/numpy/Pillow 等
- ⚡ **斜杠命令系统** — `/plan` `/yolo` `/brainstorm` `/subagent` `/skill` `/clear` `/help`，前端 `/` 按钮下拉菜单
- 🧠 **记忆系统强化** — 核心记忆自动去重 + 行数上限；CJK 中文 LIKE 降级搜索；遗忘机制（重要性衰减 + 过期清理 + Reflector forget）
- 🏪 **SkillHub 改进** — 本地技能目录 (`/catalog`)；安装状态标注；安装后用法说明；兼容性校验
- 🔗 **WebSocket 持久连接** — wsStore 全局管理，切换页面不断连
- ⌨️ **输入优化** — Enter 键换行，仅鼠标点击提交

### v2.0.0
- 工具系统全面重构（ToolDispatcher + Function Calling）
- 技能插件系统（PluginSkill + PromptSkill + skill.yaml）
- SkillHub 市场（GitHub Releases）
- 文件上传与多模态理解
- 前端 Tab 布局 + 工具调用可视化

### v1.0.0
- 基础聊天功能
- 多用户权限系统（admin/user/guest）
- 子代理系统（Code/Writing/Data/Research/Plan）
- 人格参数系统（10 项可调参数）
- 定时任务
- 自进化系统

## 许可证

MIT License
