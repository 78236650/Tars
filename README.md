# TARS AI Agent v2.0.0

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
│   │   │       └── web.py          # 网页获取
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

## 记忆系统 V3（Letta 混合模式）

TARS 采用三层记忆架构：

1. **Core Memory（4 块固定区块）** — 注入 system prompt：
   - `persona` Agent 人格定位
   - `user_profile` 用户画像（身份/技术栈/偏好）
   - `project_context` 当前项目上下文
   - `working_principles` 协作准则累积
2. **Archival Memory（长期记忆）** — embedding 检索 + Ebbinghaus 衰减
3. **Reflector（反思器）** — 每轮对话后异步更新 core + archival

Agent 通过 `core_memory_append` / `core_memory_replace` 工具自主编辑核心记忆；反思器作为兜底每轮触发。
Web 工具搜索结果通过反思器自动沉淀为 `source=web` 的 archival 记忆。

详见 [docs/superpowers/specs/2026-05-06-memory-v3-letta-design.md](docs/superpowers/specs/2026-05-06-memory-v3-letta-design.md)

## 快速开始

### 后端启动

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 启动服务（需重启以加载新模块）
python3 -m uvicorn tars.main:app --host 0.0.0.0 --port 8000 --reload
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
| GET | `/api/skillhub/search?q=xxx` | 搜索技能 |
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

### v2.0.0（当前）
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
