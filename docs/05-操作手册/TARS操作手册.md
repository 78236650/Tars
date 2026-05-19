# TARS AI Agent 操作手册

## 目录

1. [系统概述](#1-系统概述)
2. [快速开始](#2-快速开始)
3. [核心功能操作指南](#3-核心功能操作指南)
4. [高级功能详解](#4-高级功能详解)
5. [API 接口参考](#5-api-接口参考)
6. [管理与维护](#6-管理与维护)
7. [常见问题](#7-常见问题)

---

## 1. 系统概述

### 1.1 什么是 TARS

TARS 是一个高度自主、可配置的 AI Agent，灵感来自电影《星际穿越》中的机器人 TARS。它具备以下核心特性：

| 特性 | 说明 |
|------|------|
| 🎭 可调人格 | honesty、humor、initiative、empathy 四个参数实时调节 |
| 🧠 三层记忆 V3 | Core Memory（4 块固定区块）+ Archival Memory（embedding 检索）+ Reflector 反思器 |
| 🔌 可扩展工具 | 内置工具 + 技能生态系统 |
| 🔀 模型无关 | 支持 OpenRouter、Anthropic、OpenAI、Ollama |
| 🌐 多通道支持 | Web、Telegram、飞书、Webhook |
| ⚡ 流式响应 | 实时交互体验 |

### 1.2 当前版本

**v3.9.1** - Graphite Amber 视觉统一收口

### 1.3 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端层 (Vue 3)                           │
│  ChatView │ ToolsView │ MemoryView │ MeetingView │ SettingsView │
├─────────────────────────────────────────────────────────────────┤
│                        API 网关层                               │
│               WebSocket / REST API / Auth                       │
├─────────────────────────────────────────────────────────────────┤
│                        业务逻辑层                               │
│  Agent │ MemoryManager │ ToolDispatcher │ SkillRouter │ Planner │
├─────────────────────────────────────────────────────────────────┤
│                        数据层                                   │
│              SQLite + FTS5 + VectorStore                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 快速开始

### 2.1 环境要求

| 组件 | 版本要求 |
|------|---------|
| Python | 3.8+ |
| Node.js | 18+ |
| 数据库 | SQLite（内置） |

### 2.2 后端启动

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

### 2.3 前端启动

```bash
cd frontend
npm install
npm run dev
```

### 2.4 访问地址

- **前端页面**: http://localhost:5173
- **API 文档**: http://localhost:8000/docs
- **WebSocket 端点**: ws://localhost:8000/ws

---

## 3. 核心功能操作指南

### 3.1 聊天功能

#### 3.1.1 基本聊天

1. 在左侧侧栏选择或创建会话
2. 在底部输入框输入消息
3. 点击 **Send** 按钮或按 **Ctrl+Enter** 发送
4. 按 **Enter** 键换行

#### 3.1.2 斜杠命令系统

在聊天输入框输入 `/` 或点击左侧紫色 `/` 按钮，弹出命令菜单：

| 命令 | 说明 | 效果 |
|------|------|------|
| `/plan <任务>` | 规划模式 | 注入规划约束，只分析不写代码 |
| `/yolo` | 执行模式 | 注入执行约束，直接动手快速实现 |
| `/brainstorm <主题>` | 头脑风暴 | 发散思维，列举方向+选 top3 |
| `/subagent <code\|writing\|data\|research> <任务>` | 委派子代理 | 任务路由到专业子代理执行 |
| `/skill <技能名>` | 激活技能 | 启用指定 PromptSkill |
| `/clear` | 新对话 | 创建新会话，清空上下文 |
| `/help` | 帮助 | 显示所有命令列表 |

#### 3.1.3 文件上传

1. 点击输入框左侧的 📎 按钮
2. 选择文件（单文件最大 20MB，单次最多 5 个）
3. 附件预览出现在输入框上方
4. 输入文字后点击 Send

**支持格式**:
- 图片：jpg、png、gif、webp、bmp
- 文档：txt、md、pdf、docx、xlsx、csv、代码文件

### 3.2 工具调用

#### 3.2.1 内置工具列表

| 工具 | 说明 |
|------|------|
| weather | 查询全球城市天气 |
| file | 读取本地文件 |
| file_write | 文件创建/写入/追加/插入 |
| shell | Shell 命令执行（黑名单 + 危险命令确认） |
| process | 进程管理（list/start/stop/status） |
| network | 网络诊断（ping/port_check/http_test/dns_lookup） |
| cronjob | 管理定时任务 |
| web_search | 网页搜索 |
| web_fetch | 网页抓取 |
| python_exec | Python 沙箱执行 |
| memory | 记忆管理 |

#### 3.2.2 工具调用可视化

聊天面板会显示工具调用卡片：
- 工具名称和参数
- 执行状态（运行中/成功/失败）
- 执行耗时
- 输出结果

### 3.3 技能管理

#### 3.3.1 技能类型

| 类型 | 说明 | 示例 |
|------|------|------|
| PluginSkill | Python 代码插件，注册为 Tool | calculator |
| PromptSkill | Prompt 模板，注入 system prompt | code_assistant |

#### 3.3.2 默认技能

| 技能 | 类型 | 说明 |
|------|------|------|
| calculator | Plugin | 数学表达式求值 |
| code_assistant | Prompt | 代码编写/调试/审查/重构 |
| summarizer | Prompt | 结构化摘要提取 |
| translator | Prompt | 中英互译 |
| planner | Prompt | 任务分解、时间估算、优先级排序 |

#### 3.3.3 技能管理页面

在 **Tools** 页面可以：
1. 查看所有已安装技能（内置工具 / 已安装技能 / SkillHub 商店）
2. 点击查看技能详情
3. 启用/禁用技能
4. 卸载技能
5. 通过 SkillHub 安装新技能

### 3.4 记忆管理

#### 3.4.1 记忆架构

| 记忆类型 | 说明 | 存储方式 |
|----------|------|----------|
| Core Memory | 4 块固定区块，注入 system prompt | persona / user_profile / project_context / working_principles |
| Archival Memory | 长期记忆，支持语义检索 | embedding + FTS5 + 衰减评分 |
| Working Context | 会话级短期记忆 | 当前焦点实体、意图、未结话题 |

#### 3.4.2 记忆管理页面

访问 `/memory` 页面，包含三个 Tab：

**Personality（人格）**
- 调节人格参数滑块
- 编辑 Core Memory persona 块

**Recent（近期记忆）**
- 浏览 7 天内的 episodic 记忆
- 搜索、删除、手动晋升为长期记忆

**Long-term（长期记忆）**
- 按实体分组浏览
- 编辑、Pin 保护、多选合并压缩

#### 3.4.3 记忆压缩

记忆压缩引擎支持三种触发方式：
- 手动触发：在记忆管理页面点击压缩按钮
- 阈值触发：记忆数量超过阈值自动压缩
- 每日定时：凌晨 03:00 自动执行

### 3.5 模型管理

#### 3.5.1 支持的模型

**多模态模型**: llava、bakllava、llama3.2-vision、minicpm-v、qwen2-vl、qwen-vl

**原生 Function Calling 模型**: qwen3、qwen2.5、qwen2、llama3.1、llama3.2、llama3.3、mistral、mixtral、command-r、gemma2、deepseek-chat、deepseek-coder

#### 3.5.2 切换模型

1. 点击侧栏的模型选择 Popover
2. 从列表中选择目标模型
3. 系统自动切换，当前会话立即生效

---

## 4. 高级功能详解

### 4.1 任务自动化（PDCA）

#### 4.1.1 触发条件

- `/plan` 命令 → 硬指令
- 关键词（部署/构建/发布/测试等）+ 长度过滤 → 硬指令
- 含疑问词时降级为软提示

#### 4.1.2 PDCA 执行引擎

| 阶段 | 组件 | 说明 |
|------|------|------|
| Plan | TaskPlanner + TaskDetector | 生成多步执行计划 |
| Do | TaskExecutor | 自动执行，支持重试 |
| Check | StepVerifier | 6 种验证类型 |
| Act | ActPolicy | 重试×3 + 指数退避 + 询问/中止/跳过 |

#### 4.1.3 步骤验证类型

- `exit_code` - 检查退出码
- `output_contains` - 检查输出包含指定内容
- `file_exists` - 检查文件存在
- `file_contains` - 检查文件内容
- `http_status` - 检查 HTTP 状态码
- `custom` - 自定义验证逻辑

### 4.2 子代理系统

#### 4.2.1 专业子代理

| 子代理 | 专长 | 使用命令 |
|--------|------|----------|
| code | 代码编写、调试、审查 | `/subagent code <任务>` |
| writing | 写作、文案、文档 | `/subagent writing <任务>` |
| data | 数据分析、处理、可视化 | `/subagent data <任务>` |
| research | 研究、资料收集、分析 | `/subagent research <任务>` |
| plan | 规划、方案设计 | `/subagent plan <任务>` |

### 4.3 Python 沙箱执行

Agent 可写 Python 代码并在沙箱子进程中运行：

```python
python_exec(code="""
import pandas as pd
df = pd.read_csv('data.csv')
print(df.describe())
""")
```

**已安装 Python 包**: pandas、openpyxl、Pillow、pypdf、python-docx

**适用场景**: 读取 CSV/Excel/PDF、数据分析、图片处理、格式转换、快速原型

### 4.4 SkillHub 市场

#### 4.4.1 功能

- 基于 GitHub Releases 的真实技能市场
- 搜索、安装、卸载、更新技能
- 权限声明 + 安全校验
- 兼容性校验（tars_version_min + requires_packages）

#### 4.4.2 安全机制

- 安装时显示权限声明
- 危险组合（shell + network + file_write）强警告
- 运行时 permission_engine 拦截检查

---

## 5. API 接口参考

### 5.1 会话管理 `/api/sessions/`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/sessions/` | 列出会话（按 updated_at 倒序） |
| POST | `/api/sessions/` | 创建新会话 |
| GET | `/api/sessions/{id}/messages` | 获取会话历史消息 |
| DELETE | `/api/sessions/{id}` | 删除会话 + 关联消息 |
| PATCH | `/api/sessions/{id}` | 更新会话标题 |

### 5.2 工具管理 `/api/tools/`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/tools/` | 列出所有工具 |
| GET | `/api/tools/{id}` | 工具详情 |
| PUT | `/api/tools/{id}/status` | 启用/禁用 |
| PUT | `/api/tools/{id}/config` | 更新配置 |
| POST | `/api/tools/execute` | 手动执行（调试） |

### 5.3 技能管理 `/api/skills/`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/skills/` | 列出已安装技能 |
| GET | `/api/skills/{id}` | 技能详情 |
| POST | `/api/skills/create-prompt` | 创建 PromptSkill |
| PUT | `/api/skills/{id}/enable` | 启用 |
| PUT | `/api/skills/{id}/disable` | 禁用 |
| DELETE | `/api/skills/{id}` | 卸载 |

### 5.4 SkillHub `/api/skillhub/`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/skillhub/catalog` | 本地技能目录 |
| GET | `/api/skillhub/search?q=xxx` | 搜索技能 |
| GET | `/api/skillhub/detail/{id}` | 包详情 |
| POST | `/api/skillhub/install` | 安装 |
| POST | `/api/skillhub/uninstall` | 卸载 |
| GET | `/api/skillhub/installed` | 已安装列表 |
| GET | `/api/skillhub/updates` | 检查更新 |

### 5.5 文件上传 `/api/files/`

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/files/upload` | 上传文件（multipart/form-data） |
| GET | `/api/files/{file_id}` | 获取文件信息 |
| DELETE | `/api/files/{file_id}` | 删除文件 |

### 5.6 记忆管理 `/api/memory/`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/memory/core` | 获取 Core Memory |
| PUT | `/api/memory/core/{block}` | 更新 Core Memory 区块 |
| POST | `/api/memory/core/{block}/append` | 追加内容到 Core Memory |
| GET | `/api/memory/archival` | 分页获取 Archival Memory |
| POST | `/api/memory/archival` | 插入新的 Archival Memory |
| DELETE | `/api/memory/archival/{id}` | 删除 Archival Memory |
| POST | `/api/memory/compress` | 手动触发记忆压缩 |
| POST | `/api/memory/merge` | 合并多个记忆 |
| GET | `/api/memory/stats` | 获取记忆统计信息 |

### 5.7 其他 API

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/models` | 可用模型列表 |
| POST | `/api/models/switch` | 切换模型 |
| GET/PUT | `/api/personality` | 人格设置 |
| GET/PUT | `/api/subagents` | 子代理配置 |
| GET/POST/DELETE | `/api/users` | 用户管理 |
| GET/POST/DELETE | `/api/cronjobs` | 定时任务 |
| WebSocket | `/ws` | 聊天通信 |

---

## 6. 管理与维护

### 6.1 定时任务管理

TARS 支持 cron 定时任务：

```bash
# 查看所有定时任务
curl http://localhost:8000/api/cronjobs

# 创建定时任务
curl -X POST http://localhost:8000/api/cronjobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "daily_backup",
    "cron_expression": "0 3 * * *",
    "command": "backup.sh"
  }'
```

### 6.2 测试运行

```bash
cd backend
./venv/bin/python3 -m pytest tests/ -v
# 75 tests passed (39 tools/skills + 18 file upload + 18 default skills)
```

### 6.3 日志管理

日志文件位置：
- 后端日志：`backend/logs/tars.log`
- 前端日志：浏览器控制台

### 6.4 性能优化建议

1. **数据库优化**: 定期清理过期记忆（imp < 0.25 且 15 天未访问）
2. **内存管理**: 开启记忆压缩定时任务
3. **模型选择**: 根据任务类型选择合适的模型
4. **缓存策略**: 利用语义缓存减少重复计算

---

## 7. 常见问题

### Q1: 为什么工具调用没有响应？

**可能原因**:
1. 模型不支持 Function Calling，需要等待 Prompt Fallback 处理
2. 工具参数格式错误
3. 网络超时

**解决方案**:
- 检查模型是否在支持列表中
- 查看 API 响应状态
- 增加超时时间配置

### Q2: 图片上传后无法识别？

**可能原因**:
1. 使用的是非多模态模型
2. 未安装 Tesseract OCR

**解决方案**:
- 切换到多模态模型（如 llava）
- 安装 Tesseract OCR：
  - macOS: `brew install tesseract tesseract-lang`
  - Ubuntu: `apt install tesseract-ocr tesseract-ocr-chi-sim`

### Q3: 记忆内容不显示？

**可能原因**:
1. 记忆检索未命中
2. 重要性衰减过低

**解决方案**:
- 检查检索关键词是否准确
- 手动提升重要性评分
- 查看记忆统计确认数据存在

### Q4: 技能安装失败？

**可能原因**:
1. 版本不兼容
2. 依赖包缺失
3. 权限不足

**解决方案**:
- 检查 `tars_version_min` 要求
- 安装所需依赖包
- 检查文件系统权限

### Q5: WebSocket 连接断开？

**可能原因**:
1. 网络不稳定
2. 服务重启
3. 会话超时

**解决方案**:
- 前端会自动重连
- 刷新页面
- 检查后端服务状态

---

## 附录

### 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+Enter | 发送消息 |
| Ctrl+/ | 打开命令面板 |
| Ctrl+L | 新建会话 |
| ESC | 关闭弹窗/抽屉 |

### 文件大小限制

| 类型 | 限制 |
|------|------|
| 单文件 | 20MB |
| 单次附件数 | 5 个 |
| 文本文件 | 30000 字符 |
| OCR 文本 | 5000 字符 |

### 许可证

MIT License

---

*文档版本: v3.9.1*  
*创建日期: 2026-05-19*