# 任务自动化设计（E1）

- **日期**：2026-05-09
- **版本**：v1.3
- **状态**：草稿
- **更新**：融合 Agent Skills（Skills as SOP）+ PDCA 执行控制框架 + TaskWorkspace

## 一、背景与目标

### 1.1 现状痛点

TARS v2.3 已具备：
- **TaskPlannerTool** — LLM 生成多步执行计划
- **TaskExecutor** — 自动按步骤执行 + 重试机制

但用户需要**主动触发**这些功能，无法享受"AI 自动识别并规划"的能力。

### 1.2 目标

建立**任务自动识别与执行**系统：
- TARS 自动检测复杂任务，询问用户是否需要规划执行
- 用户确认后，TARS 自动拆分任务、逐步执行、实时汇报
- 结果在独立任务面板中呈现，不阻塞对话

### 1.3 非目标

- 不做全自动执行（始终需要用户确认）
- 不做跨系统工作流（如 Zapier 风格）
- 不做复杂依赖图解析

---

## 二、理论基础

### 2.1 框架概述

本设计融合两大理念：

| 框架 | 层级 | 作用 |
|------|------|------|
| **Agent Skills** | 任务定义层 | 定义"怎么做"（SOP 标准操作程序） |
| **PDCA 循环** | 执行控制层 | 循环执行 + 验证反馈 |

**核心思想**：Skills = SOP（最佳实践模板），TaskExecutor 按 PDCA 循环执行。

### 2.2 Agent Skills 理念

**来源**：Anthropic Claude Code 2025年10月引入，2026年已成为开放标准（agentskills.io）

**核心理念**：
- **Skills vs Tools**：Tools = "能做什么"；Skills = "怎么做得更好"
- **Progressive Disclosure**：按需加载，只在需要时注入完整上下文
- **SOP 即代码**：将领域知识封装为可执行的技能包

### 2.3 PDCA 循环

**PDCA 循环**（Plan-Do-Check-Act）作为执行控制框架：

| 阶段 | 含义 | 在本系统中的实现 |
|------|------|------------------|
| **Plan（计划）** | 分析问题，制定行动方案 | 加载/生成 Skill SOP |
| **Do（执行）** | 按计划执行 | TaskExecutor 执行每个步骤 |
| **Check（检查）** | 验证执行结果 | Skill 定义的验证条件 |
| **Act（行动）** | 根据结果调整 | 失败时决定重试/跳过/中止 |

### 2.4 Skills + PDCA 融合

```
┌──────────────────────────────────────────────────────────────┐
│                    Agent Skills（任务定义层）                  │
│                                                              │
│  SKILL.md                                                    │
│    ├── name/description     → 触发条件匹配                    │
│    ├── steps               → Plan 生成步骤                   │
│    ├── verify              → Check 验证条件                   │
│    └── fallback            → Act 失败处理                     │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    PDCA 循环（执行控制层）                     │
│                                                              │
│  Plan ───→ Do ───→ Check ───→ Act                          │
│    ↑                  │      │                              │
│    │                  │      └── 验证失败？→ 重试/跳过/中止  │
│    └──────────────────┴──────────────────────────────────    │
└──────────────────────────────────────────────────────────────┘
```

### 2.5 Progressive Disclosure 实现

Agent Skills 的按需加载机制：

| 阶段 | Token 预算 | 内容 |
|------|-----------|------|
| **1. Advertise** | ~100 tokens/skill | Skill 名称 + 描述，注入 system prompt |
| **2. Load** | <5000 tokens | 匹配时加载完整 SKILL.md |
| **3. Read** | as needed | 按需读取 references/ 目录 |
| **4. Execute** | — | 执行 Skill 定义的操作 |

---

## 三、任务 Skill 定义

### 3.1 Skill 结构

每个任务 Skill 是一个目录，遵循 Agent Skills 开放标准：

```
~/.tars/task_skills/
├── deploy-project/           # 项目部署技能
│   ├── SKILL.md             # 技能定义
│   └── scripts/
│       └── health_check.sh  # 健康检查脚本
├── code-review/              # 代码审查技能
│   ├── SKILL.md
│   └── scripts/
│       └── lint.sh
└── data-analysis/           # 数据分析技能
    ├── SKILL.md
    └── templates/
        └── report.md
```

### 3.2 SKILL.md 格式

```yaml
---
name: deploy-project
description: |
  项目部署自动化流程。适用于"帮我部署"、"发布到服务器"、"deploy"等请求。
  会自动检测 git 状态、运行构建、验证部署结果。
trigger_keywords: ["部署", "发布", "deploy", "发布到", "上线"]
compatibility: 需要 git + npm/node 环境
allowed_tools:
  - git
  - shell
  - file_read
  - file_write
---

## 执行步骤

### 1. 前置检查
- 描述：检查 git 状态，确保工作区干净
- 命令：git status --porcelain
- 验证：
  - type: output_is_empty
  - error_msg: "工作区有未提交的更改，请先 commit"

### 2. 安装依赖
- 描述：安装项目依赖
- 命令：npm install
- 验证：
  - type: output_not_contains
  - expected: "ERR!"
  - error_msg: "依赖安装失败"

### 3. 构建
- 描述：执行生产构建
- 命令：npm run build
- 验证：
  - type: file_exists
  - expected: "dist/index.html"
  - error_msg: "构建产物不存在"

### 4. 部署（可选）
- 描述：部署到服务器
- 命令：scp -r dist/* user@server:/var/www/app/
- 验证：
  - type: exit_code
  - expected: 0
  - error_msg: "部署失败"

### 5. 健康检查
- 描述：验证部署结果
- 命令：curl -s -o /dev/null -w "%{http_code}" http://example.com
- 验证：
  - type: output_contains
  - expected: "200"
  - error_msg: "服务不可用"

## 失败处理

### 可跳过的步骤
- 步骤 4（部署）：如果用户没有配置服务器，可以跳过

### 不可跳过的步骤
- 步骤 1、2、3、5 必须成功才能继续

### 重试策略
- 步骤 2、3：最多重试 2 次
- 步骤 4、5：最多重试 3 次
```

### 3.3 内置 Task Skills

TARS 提供以下内置 Task Skills：

| Skill | 触发关键词 | 适用场景 |
|-------|-----------|----------|
| `deploy-project` | 部署、发布、deploy、上线 | 前端/Node.js 项目部署 |
| `code-review` | 审查、review、代码检查 | 代码审查流程 |
| `test-runner` | 测试、test、跑测试 | 运行单元/集成测试 |
| `data-analysis` | 分析、数据、报表 | 数据分析任务 |
| `git-workflow` | commit、git、提交 | Git 工作流 |
| `file-convert` | 转换、convert、格式转换 | 文件格式转换 |

### 3.4 Skill 注册与发现

**Advertise 阶段**（~100 tokens）：
- 系统启动时，扫描 `~/.tars/task_skills/` 目录
- 提取每个 Skill 的 `name` + `description` + `trigger_keywords`
- 注入到 Agent 的 system prompt

**Load 阶段**（按需加载）：
- TaskDetector 检测到匹配的触发词
- 加载对应 Skill 的完整 SKILL.md
- 将步骤注入 TaskPlanner

### 3.5 步骤验证机制（Check）

每个步骤包含**执行**和**验证**两部分：

```json
{
  "step_order": 1,
  "description": "git pull 拉取最新代码",
  "command": "git pull origin main",
  "verify": {
    "type": "exit_code",
    "expected": 0,
    "error_msg": "拉取代码失败"
  }
}
```

**验证类型**：

| 类型 | 说明 | 示例 |
|------|------|------|
| `exit_code` | 检查退出码 | git pull 成功返回 0 |
| `output_contains` | 输出包含关键字 | 包含 "Already up to date" |
| `output_not_contains` | 输出不包含错误 | 不包含 "error" |
| `output_is_empty` | 输出为空 | git status 无输出 |
| `file_exists` | 文件存在 | package.json 存在 |
| `file_not_exists` | 文件不存在 | 无 node_modules |
| `custom` | 自定义验证 | 调用 LLM 判断结果 |

**验证失败处理（Act）**：

```
验证失败
    │
    ├── 重试（Retry）— 最多 3 次
    │       │
    │       └── 成功 → 继续下一步
    │       └── 失败 → 进入跳过/中止判断
    │
    ├── 跳过（Skip）— 标记为 skipped，继续下一步
    │
    └── 中止（Abort）— 任务失败
```

---

## 四、TaskWorkspace 机制

### 4.1 设计原则

**默认使用本地文件夹**：任务相关文件在用户的项目目录下操作，不强制使用 git 仓库。

### 4.2 Workspace 自动创建

当用户创建任务但没有可用的工作目录时，TARS 自动创建：

```
任务 Workspace 目录结构：
~/.tars/workspaces/
└── {日期时间}_{任务标题_slug}/
    ├── .git/                    # 自动初始化为 git 仓库
    ├── task.md                  # 任务描述
    ├── steps.json              # 执行步骤记录
    ├── outputs/                 # 输出文件目录
    └── logs/                    # 执行日志目录
```

**命名规则**：
- 目录名：`20260509_143052_项目部署`（格式：`{日期}{时间}_{标题slug}`）
- slug：中文转拼音/英文，小写化，空格替换为 `_`

### 4.3 Workspace 上下文检测

TaskPlanner 在生成计划前，先检测可用环境：

```python
def detect_workspace_context(user_msg: str) -> dict:
    """检测工作区上下文，返回可用操作列表"""
    result = {
        "has_git": False,
        "has_remote": False,
        "workspace_path": None,
        "available_ops": []
    }

    # 1. 检测用户是否在某个项目目录下
    workspace = get_current_workspace()
    if workspace:
        result["workspace_path"] = workspace

        # 2. 检测是否是 git 仓库
        if is_git_repo(workspace):
            result["has_git"] = True
            result["available_ops"].extend(["add", "commit", "status", "log", "diff"])

            # 3. 检测是否有远程仓库
            remotes = get_git_remotes(workspace)
            if remotes:
                result["has_remote"] = True
                result["available_ops"].extend(["push", "pull", "fetch"])

        # 4. 检测可用的构建工具
        result["available_ops"].extend(detect_build_tools(workspace))

    return result
```

### 4.4 Git 仓库初始化流程

```
用户创建任务
    │
    ▼
检测是否有可用 workspace
    │
    ├── 有
    │   └── 检测 git 状态，添加到 available_ops
    │
    └── 无
        └── 创建 TaskWorkspace
                │
                ▼
            初始化为 git 仓库
                │
                ▼
            生成任务计划（基于可用操作）
```

### 4.5 操作分层

根据检测到的上下文，TaskPlanner 限制可用操作：

| 场景 | 可用 Git 操作 | 可用其他操作 |
|------|--------------|--------------|
| 无 workspace | init（新建） | mkdir/copy |
| 本地 git | add/commit/status/log/diff | 文件操作 |
| git + 远程 | + push/pull/clone/fetch | + scp/docker |
| 非 git 项目 | 无 git 操作 | 文件操作/构建/测试 |

**注意**：如果项目已有 git 仓库，TARS **不会**在子目录创建新的仓库，而是在原仓库内操作。

---

## 五、核心组件

### 5.1 TaskDetector

**职责**：分析用户消息，判断是否触发任务自动化

**触发条件**（满足任一）：
1. 消息包含明确的操作意图：
   - "帮我部署"
   - "构建并发布"
   - "跑一下测试"
   - "部署到服务器"
2. 消息涉及多步骤操作（LLM 判断）
3. 用户明确使用 `/plan` 命令

**实现**：
- 在 Agent 主循环中，消息预处理阶段调用
- 使用 Scene Analyzer 的意图识别能力（已支持 `intent: planning.*`）
- 触发时生成询问 prompt，注入 system prompt

**Prompt 示例**：
```
检测到用户可能需要任务自动化。是否需要我帮你规划并执行？

用户输入：{user_msg}
检测到的意图：{intent}
```

### 5.2 TaskPanel（前端）

**职责**：独立任务面板，展示和管理所有任务

**页面位置**：
- 新增 `/tasks` 路由
- 可从侧边栏"任务"入口进入

**UI 布局**：
```
┌─────────────────────────────────────────┐
│ 任务面板                        [关闭] │
├─────────────────────────────────────────┤
│ [全部] [进行中] [已完成] [失败]          │
├─────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐ │
│ │ 🔄 项目部署 #001           进行中    │ │
│ │ ─────────────────────────────────── │ │
│ │ ✓ 1. git pull                      │ │
│ │ ◐ 2. npm build          [查看日志]  │ │
│ │ ○ 3. 部署到服务器                   │ │
│ │ ○ 4. 验证部署结果                   │ │
│ │                        [暂停] [取消]│ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ ✅ 代码审查 #002           已完成    │ │
│ │ ─────────────────────────────────── │ │
│ │ ✓ 1. 运行 ESLint                    │ │
│ │ ✓ 2. 运行单元测试                    │ │
│ │ ✓ 3. 生成审查报告                    │ │
│ │                        [查看报告]  │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**任务卡片状态**：
| 状态 | 图标 | 颜色 |
|------|------|------|
| 等待确认 | ⏸ | 灰色 |
| 进行中 | 🔄 | 蓝色 |
| 暂停 | ⏸ | 黄色 |
| 已完成 | ✅ | 绿色 |
| 失败 | ❌ | 红色 |

**交互**：
- 点击任务卡片：展开/收起详情
- 点击步骤：查看该步骤的执行日志
- 暂停/恢复：暂停任务执行
- 取消：终止任务（不可恢复）
- 重试：重新执行失败的任务

### 5.3 TaskExecutor（增强）

**复用现有**：`backend/tars/orchestration/executor.py`

**增强点**：
1. **异步执行**：不阻塞主对话
2. **状态持久化**：任务状态存入数据库
3. **WebSocket 推送**：实时更新前端面板
4. **危险操作拦截**：危险命令执行前暂停，等待用户确认

### 5.4 危险操作处理

**黑名单命令**（来自现有 shell 工具）：
- `rm -rf`
- `mkfs`
- `dd if=`
- `> /dev/sd*`

**确认流程**：
```
1. TaskExecutor 检测到危险命令
2. 任务状态设为 "待确认"
3. WebSocket 推送确认请求到前端
4. 前端弹出确认框，显示命令详情
5. 用户确认 → 继续执行
6. 用户拒绝 → 跳过该步骤或取消任务
```

**高风险命令**（rm 等）额外二次确认：
```
⚠️ 即将执行危险命令：rm -rf node_modules
输入 "yes" 确认执行：
[     ]
```

---

## 六、数据模型

### 6.1 数据库表：tasks

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    skill_name TEXT,              -- 使用的 Skill 名称
    status TEXT DEFAULT 'pending',  -- pending/confirmed/running/paused/completed/failed
    current_step INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 0,
    workspace_path TEXT,           -- TaskWorkspace 路径
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    error_message TEXT
);
```

### 6.2 数据库表：task_steps

```sql
CREATE TABLE task_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    step_order INTEGER NOT NULL,
    description TEXT NOT NULL,
    command TEXT,
    verify_type TEXT,            -- exit_code/output_contains/file_exists/output_is_empty
    verify_expected TEXT,        -- 期望值
    verify_msg TEXT,             -- 失败提示
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    skippable BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'pending', -- pending/running/completed/skipped/failed
    result TEXT,
    error TEXT,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

### 6.3 WebSocket 消息

```typescript
interface TaskEvent {
  type: 'task_created' | 'task_updated' | 'step_updated' | 'confirmation_needed' | 'task_completed';
  payload: {
    task_id: string;
    task?: Task;
    step?: TaskStep;
    confirmation?: ConfirmationRequest;
  };
}

interface ConfirmationRequest {
  step_id: number;
  command: string;
  risk_level: 'high' | 'critical';
  message: string;
}
```

---

## 七、API 设计

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/tasks/` | GET | 列出用户的所有任务 |
| `/api/tasks/` | POST | 创建新任务 |
| `/api/tasks/{id}` | GET | 获取任务详情（含步骤） |
| `/api/tasks/{id}/confirm` | POST | 用户确认危险操作 |
| `/api/tasks/{id}/pause` | POST | 暂停任务 |
| `/api/tasks/{id}/resume` | POST | 恢复任务 |
| `/api/tasks/{id}/cancel` | POST | 取消任务 |
| `/api/tasks/{id}/retry` | POST | 重试失败任务 |
| `/api/tasks/{id}/steps/{step_id}/logs` | GET | 获取步骤执行日志 |
| `/api/taskskills/` | GET | 列出所有可用 Task Skills |
| `/api/taskskills/{name}` | GET | 获取 Skill 详情 |

---

## 八、流程图

### 8.1 任务创建流程

```
用户: "帮我部署项目"
    │
    ▼
TaskDetector 分析
    │
    ▼
检测到需要自动化
    │
    ▼
询问用户: "需要我帮你规划执行吗？"
    │
    ├─ 用户拒绝 → 正常对话
    │
    └─ 用户确认
            │
            ▼
        检测/创建 TaskWorkspace
            │
            ▼
        加载匹配的 Task Skill
            │
            ▼
        TaskPlanner 生成计划
            │
            ▼
        创建 Task + TaskSteps
            │
            ▼
        WebSocket 推送任务卡片
            │
            ▼
        TaskExecutor 开始执行
            │
            ├─ 危险命令 → 暂停 → 等待确认 → 继续
            │
            └─ 执行完成 → 更新状态 → 通知用户
```

### 8.2 前端交互流程

```
用户点击"确认执行"
    │
    ▼
POST /api/tasks/{id}/confirm
    │
    ▼
TaskExecutor 继续执行
    │
    ▼
WebSocket 推送 step_updated
    │
    ▼
前端更新步骤状态
    │
    ▼
任务完成 → 推送 task_completed
```

---

## 九、开发任务分解

### Phase 1: 后端核心
1. 新增 `tasks` / `task_steps` 数据库表
2. 新增 `api/tasks.py` 和 `api/taskskills.py` 路由
3. 实现 Task Skill 加载器（复用现有 SkillLoader）
4. 增强 `TaskExecutor` 支持异步 + 状态持久化 + 验证
5. WebSocket 推送任务状态

### Phase 2: 前端核心
1. 新增 `/tasks` 路由和 `TasksView.vue`
2. 实现 `TaskPanel.vue` 组件
3. 实现 `TaskCard.vue` 组件
4. 实现危险操作确认弹窗
5. 集成 SkillHub 技能列表

### Phase 3: 集成
1. TaskDetector 集成到 Agent
2. 实现 TaskWorkspace 自动创建
3. 完善错误处理
4. 测试全流程

---

## 十、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 执行时间过长 | 用户等待焦虑 | 显示预估时间 + 实时进度 |
| 危险命令误执行 | 数据丢失 | 双确认机制 + 黑名单 |
| 执行失败 | 任务状态不一致 | 完整的状态机 + 回滚机制 |
| WebSocket 断开 | 状态更新丢失 | 轮询兜底 + 状态持久化 |

---

## 十一、非目标（明确）

- 不做全自动化执行（用户必须确认）
- 不做任务依赖图
- 不做定时任务调度
- 不做任务模板库（Skill 即模板）

---

*文档版本: v1.3*
*日期: 2026-05-09*
*更新: 融合 Agent Skills（Skills as SOP）+ PDCA 执行控制框架 + TaskWorkspace 机制*
