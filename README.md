# TARS AI Agent v4.1.0

一个完整的 AI 助手应用，支持多用户权限管理、SkillHub 本地技能生态、知识库主动检索、Admin 管理台、专业子代理委派、可配置人格参数、工具调用（Function Calling）、技能插件系统、文件上传与多模态理解、记忆可视化管理与自动压缩。

> **当前版本 v4.1.0** — 详见 [Changelog](docs/01-项目概览/changelog.md) | v4.0.5 [发布说明](docs/01-项目概览/v4.0.5-release-notes.md)

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
│   │   │   ├── compressor.py       # 记忆压缩引擎（摘要合并 + 层级归档）
│   │   │   ├── scheduler.py        # 压缩定时调度（每日 03:00 + 阈值触发）
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
└── frontend/                       # 前端（Vue 3 + TypeScript + TailwindCSS）
    └── src/
        ├── views/
        │   ├── ChatView.vue        # 聊天页（快捷键 + 文件上传 + 命令菜单）
        │   ├── ToolsView.vue       # 工具管理（Tab 布局 + SkillHub 目录）
        │   ├── ModelsView.vue      # 模型管理
        │   └── SettingsView.vue    # 设置页
        ├── components/
        │   ├── chat/
        │   │   ├── ChatPanel.vue   # 聊天面板（★Markdown渲染 + 代码高亮 + 欢迎卡片）
        │   │   └── PlanCard.vue    # 任务计划执行卡片
        │   ├── layout/
        │   │   └── Sidebar.vue     # 侧栏（★搜索/分组/Popover模型切换）
        │   └── tools/              # 工具卡片/详情/添加
        ├── stores/
        │   └── wsStore.ts          # WebSocket 全局状态
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

## v2.2.0 新特性 — 记忆认知架构

### 四层记忆

- **Core Memory**（4 块固定区块）— Letta 模式不变画像
- **Working Context**（会话级短期）— 当前焦点实体、意图、未结话题
- **Semantic Memory**（实体图）— `entities` + `relations` 表，哈希 ID + aliases 合并
- **Episodic Memory**（事件流）— archival 升级，带 `event_time` / `entity_refs` / `supersedes`

### Scene Analyzer + MemoryRouter + SkillRouter

- **Scene Analyzer** — 每轮小模型分析意图、焦点实体、是否需要记忆召回；带 fast_path 跳过 + 语义缓存
- **MemoryRouter** — 实体/时间线/向量/关键词四路融合打分，异常时降级 HybridSearch
- **SkillRouter** — `trigger.intents/entities/keywords` + priority 动态选技能，淘汰永久注入
- **Hooks** — `on_activate` / `pre_llm` / `post_llm`，2s 超时沙箱化

### Reflector 异步分流

- 6 种操作：`upsert_entity` / `upsert_relation` / `log_episode` / `update_core` / `forget` / `noop`
- 异步队列批处理，紧急写入通道（`core_memory_append` / `archival_insert`）绕过队列同步写

## v2.4.0 新特性 — 任务自动化（PDCA）

### TaskDetector + 三档触发

- `/plan` 命令 → 硬指令
- 关键词（`部署`/`构建`/`发布`/`测试` 等）+ 长度过滤 → 硬指令
- 含疑问词时降级软提示，避免询问类消息被误判为执行意图

### PDCA 执行引擎

- **Plan**：TaskPlanner（已有）+ TaskDetector（新）
- **Do**：TaskExecutor 复用 v2.1，新增危险命令拦截
- **Check**：StepVerifier 6 种验证类型 (`exit_code` / `output_contains` / `file_exists` 等)
- **Act**：ActPolicy 重试×3 + 指数退避 + 询问/中止/跳过

### Workspace 解析

- 4 级优先级：API → WorkspaceManager → `Path(__file__).resolve().parent.parent.parent` → `~/.tars/workspaces/{slug}/`
- `tars_repo_root` 兜底命中时前端强制确认

### SQLite 持久化 + 崩溃恢复

- `tasks` / `task_steps` 表带 status / verify_type / artifacts / output_summary
- 启动时扫描 `running/paused` 任务置为 paused，用户手动恢复

### 前端 TaskPanel

- ChatView 内嵌右侧抽屉，响应式三档断点（≥1200/900-1199/<900）
- 步骤实时状态 + retries 黄色标识 + 产出文件可点击

## v2.5.0 新特性 — 技能 Agent Skills 化

### 完全对齐 Anthropic Agent Skills 规范

- 主文件 `SKILL.md`（YAML frontmatter + Markdown 正文），只需 `name` + `description`
- 渐进披露：LLM 读 description 自判激活，淘汰关键词 + Router 打分
- 目录结构：`skills/<name>/{SKILL.md, pdca.yaml, scripts/, references/, assets/}`
- 可直接导入 `anthropics/skills` 社区技能

### PDCA 挂件

- 需要确定性的技能挂 `pdca.yaml`，LLM 调 `task_planner(pdca_ref="skill://deploy/pdca.yaml")` 触发
- 复用 v2.4 TaskExecutor + StepVerifier + ActPolicy
- 变量替换 `{{workspace.pm}}` / `{{workspace.branch}}` 按 tool_name 分类 shlex.quote 防注入

### 内置三个 PDCA 示范技能

- `deploy` — 构建部署项目
- `run_tests` — 检测 framework + 跑测试 + 解析报告
- `release_notes` — 从 git log 生成 CHANGELOG（动态 task_planner 步骤，非 pdca.yaml）

### 权限模型

- SKILL.md 声明 `permissions: [shell, file_write, git_push, network, system]`
- 安装时用户授权 + 运行时 `permission_engine.can_call` 拦截
- 危险组合（shell + network + file_write）安装时强警告

### 迁移工具

- `scripts/migrate_skill_yaml_to_md.py` 把 v2.2 私有格式自动转 SKILL.md

## v2.6.0 新特性 — 工具调用稳定性 + 上传发布

### 修复 web_search / web_fetch 工具不可用

- **Ollama 400 Bad Request**：dispatcher 不再把 `tool_calls[].function.arguments` 序列化成字符串；ollama.py 发送前确保是 dict；OpenAI 协议 (Custom/OpenRouter) 仍按规范序列化为 JSON 字符串
- **CustomProvider 返回格式归一化**：阿里 API 的 `choices[0].message.tool_calls` 嵌套结构展平为 dispatcher 期望的扁平 dict，工具结果正确传回 LLM
- **OpenRouter tool_calls 字段补齐**：之前丢失 tool_calls 透传
- **工具调用强制非流式**：`tools` 参数存在时关闭 stream，确保 tool_calls 完整接收
- **tool_call_id 唯一化**：`call_{uuid4}` 替代 `call_{tool_name}`，多轮同名工具不冲突
- **NATIVE_TOOL_MODELS 扩展**：增加 `qwen-max` / `qwen-plus` / `qwen-turbo` / `kimi` 等云端模型

### v2.5 修复轮

- SKILL.md 加载支持 PluginSkill（目录含 `main.py` 自动按 plugin 注册到 ToolRegistry）
- `INSERT INTO tasks` 改显式列名，匹配 ALTER 后的 17 列
- 权限引擎与渐进披露联动，从 `pdca_ref` 反推 `skill_id` 自动设 `_active_skill_id`
- VariableEngine 按 `tool_name` 分类 `shlex.quote`，`{{step_N.*}}` 保留给 executor 运行时处理
- pdca.yaml 的 `act` 字段注入 TaskExecutor.act_policy（max_retries / retry_backoff / on_final_failure）

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
- marked（Markdown 渲染）
- highlight.js（代码语法高亮）

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

### v2.3.0（当前）
- 🎨 **前端重设计** — 欢迎页快捷入口卡片 + 消息卡片式布局 + 命令彩色横幅
- 📝 **Markdown 渲染** — marked.js + highlight.js 语法高亮（13 种语言按需加载）
- 📋 **代码块复制按钮** — 一键复制代码，带 ✓ 反馈动画
- 🔍 **侧栏瘦身** — 模型选择从大面板改为单行 Popover，会话列表释放全部空间
- 🔎 **会话搜索/分组** — 实时搜索 + 今天/昨天/更早分组
- ⌨️ **键盘快捷键** — Ctrl+Enter 发送 / Ctrl+/ 命令面板 / Ctrl+L 新会话
- 📏 **输入框自适应高度** — 内容超过 1 行自动增高（最多 6 行）
- 🖼️ **自定义 Logo** — 支持 PNG favicon + 侧栏/Header 图片 Logo
- ⚡ **highlight.js 按需加载** — ChatView.js 从 1002KB 缩减到 132KB（-87%）
- 🔧 **PLAN/BRAINSTORM 提示词精简** — prompt 从 103 字符减到 49 字符，防止 LLM 卡死
- ⏱️ **工具调用耗时显示** — 前端工具卡片展示每个工具执行时长
- 🏠 **默认 SOUL.md 更新** — 反映 TARS 工程助手定位 + 实际工具列表
- 🔄 **ToolDispatcher 降级增强** — 空响应时自动去工具重试 + 追加总结请求

### v2.2.0
- 🧠 **记忆认知架构重做** — 场景画像 + 实体图 + 事件时间线 + 四路融合检索
- 🗂️ **Semantic Memory（实体图）** — 确定性哈希 ID + aliases FTS5 合并，防止同名实体分裂
- 🔀 **MemoryRouter** — 实体路/时间线路/向量路/关键词路四路融合 + HybridSearch 异常兜底
- ⚡ **SkillRouter** — 基于意图+实体+关键词的动态技能激活，替代永久注入
- 🪝 **Skill Hooks** — on_activate/pre_llm/post_llm 三阶段钩子 + SkillContext
- 🔍 **Scene Analyzer** — 同步意图识别 + fast_path 跳过 + semantic cache
- 📝 **Reflector 重做** — upsert_entity/upsert_relation/log_episode 分流写入 + project_context 自动派生
- 🆘 **紧急写入通道** — `archival_insert` 工具，用户说"记住X"时同步写入
- 🗑️ **遗忘机制** — 重要性自然衰减 + 过期自动清理 + Reflector forget

### v2.1.0
- 🚀 **Python 沙箱执行** (`python_exec`) — Agent 可写 Python 代码并执行，支持 pandas/numpy/Pillow 等
- ⚡ **斜杠命令系统** — `/plan` `/yolo` `/brainstorm` `/subagent` `/skill` `/clear` `/help`，前端 `/` 按钮下拉菜单
- 🧠 **记忆系统强化** — 核心记忆自动去重 + 行数上限；CJK 中文 LIKE 降级搜索；遗忘机制（重要性衰减 + 过期清理 + Reflector forget）
- 🏪 **SkillHub 改进** — 本地技能目录 (`/catalog`)；安装状态标注；安装后用法说明；兼容性校验
- 🔗 **WebSocket 持久连接** — wsStore 全局管理，切换页面不断连
### v3.9.0
- 🧠 **记忆管理页面** — 独立一级页面 `/memory`，Tab 切换（人格 / 近期记忆 / 长期记忆）
- 🎛️ **人格编辑迁移** — PersonalitySettings 从 Settings 迁入记忆页面，统一管理滑块参数 + Core Memory persona 块
- 📋 **近期记忆管理** — 7 天内 episodic 记忆浏览、搜索、删除、手动晋升为长期记忆
- 📦 **长期记忆管理** — 按实体分组、编辑、Pin 保护、多选合并压缩
- 🗜️ **记忆压缩引擎** — 摘要合并 + 层级归档，支持手动触发 / 阈值触发 / 每日定时兜底
- 🔧 **Memory REST API** — 12 个端点（CRUD + stats + compress + merge）
- ⚡ **性能优化** — SQL 层分页、stats 查询合并、entity_refs 索引、混合格式兼容修复

### v3.9.1
- 🎨 **Graphite Amber 视觉统一收口** — 全站深色暖系改造，琥珀（amber）替换蓝色（blue）主色调
- 🖥️ **DesktopShell 桌面态可折叠窄栏** — 右栏支持展开/折叠态，localStorage 持久化，48px 窄栏 + 展开恢复把手
- 📦 **通用弹层壳 AppSurfaceDialog / AppSurfaceDrawer** — 统一视觉边界，居中弹窗 + 侧边抽屉，覆盖 Tools/Memory/Knowledge/BI/Settings 核心弹层
- 🎙️ **会议助手视觉统一** — MeetingSettings / RecordingPanel / TranscriptionList / TranscriptionDetail / SchemaAnnotator 全链路深色化
- 🧠 **记忆助手视觉统一** — MemoryCard / RecentMemoryTab / LongtermMemoryTab / AllMemoryTab 全链路深色化
- 📈 **BI 工作台视觉统一** — DataSourceSettings / BiAnalyticsView 深色化
- 💬 **Chat 聊天气泡统一** — 工具调用卡片/步骤面板/代码块/表格/内联代码全部改琥珀色系，ChartRenderer 按需加载
- ⚡ **ESC 键盘关闭** — AppSurfaceDialog / AppSurfaceDrawer 支持 ESC 键关闭
- 🧭 **侧栏快捷图标** — 折叠态新增设置 / 模型 / 语言切换快捷入口
- 🔍 **记忆助手滚动修复** — MemoryView / MeetingView 滚动溢出问题修复
- ✅ **19 个前端单元测试全通过**

### v2.8.1
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
