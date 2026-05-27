---
doc_type: spec
status: superseded
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# 任务自动化设计（E1）

- **日期**：2026-05-09
- **版本**：v1.2
- **状态**：草稿
- **更新**：增加 PDCA 循环 + TaskWorkspace 机制（默认本地目录，自动初始化 git 仓库）

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

## 二、理论基础

### 2.1 PDCA 循环

本设计引入 **PDCA 循环**（Plan-Do-Check-Act）作为任务执行的理论框架：

| 阶段 | 含义 | 在本系统中的实现 |
|------|------|------------------|
| **Plan（计划）** | 分析问题，制定行动方案 | TaskPlanner 生成执行步骤 |
| **Do（执行）** | 按计划执行 | TaskExecutor 执行每个步骤 |
| **Check（检查）** | 验证执行结果 | 步骤执行后验证结果 |
| **Act（行动）** | 根据结果调整 | 失败时决定重试/跳过/中止 |

**为什么选择 PDCA**：
- 简单易懂，易于实现
- 每步都有反馈循环，适合自动化场景
- 避免盲目执行，提供"检查"保障

### 2.2 当前设计与 PDCA 的对应

```
┌─────────────────────────────────────────────────────────────┐
│                        PDCA 循环                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Plan ──────→ Do ──────→ Check ──────→ Act               │
│     ↑                                            │          │
│     │                                            │          │
│     └────────────────────────────────────────────┘          │
│                         循环迭代                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘

在 TARS 中的实现：

Plan：TaskPlanner 生成 { step: "git pull", verify: "检查文件是否存在" }
Do：  TaskExecutor 执行 git pull
Check：验证执行结果（退出码、输出内容）
Act：  成功 → 下一步骤；失败 → 重试/跳过/中止
```

### 2.3 步骤验证机制（Check）

每个步骤包含**执行**和**验证**两部分：

```json
{
  "step_order": 1,
  "description": "git pull 拉取最新代码",
  "command": "git pull origin main",
  "verify": {
    "type": "exit_code",      // 或 "output_contains" / "file_exists"
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
| `file_exists` | 文件存在 | package.json 存在 |
| `file_not_exists` | 文件不存在 | 无 node_modules（构建前清理） |
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
    ├── 跳过（Skip）— 用户选择或自动判断
    │       │
    │       └── 标记为 skipped，继续下一步
    │
    └── 中止（Abort）— 任务失败
            │
            └── 更新任务状态为 failed
```

### 2.4 增强的数据模型

**task_steps 表新增验证字段**：

```sql
ALTER TABLE task_steps ADD COLUMN verify_type TEXT;      -- exit_code/output_contains/file_exists
ALTER TABLE task_steps ADD COLUMN verify_expected TEXT;  -- 期望值
ALTER TABLE task_steps ADD COLUMN verify_msg TEXT;        -- 失败提示
ALTER TABLE task_steps ADD COLUMN retry_count INTEGER DEFAULT 0;
```

**TaskPlanner 输出格式增强**：

```json
{
  "steps": [
    {
      "description": "git pull 拉取最新代码",
      "command": "git pull origin main",
      "verify": {
        "type": "exit_code",
        "expected": 0
      }
    },
    {
      "description": "npm install 安装依赖",
      "command": "npm install",
      "verify": {
        "type": "output_not_contains",
        "expected": "ERR!",
        "error_msg": "依赖安装失败"
      }
    }
  ]
}
```

## 三、总体架构

```
用户消息
    │
    ▼
┌─────────────────┐
│ TaskDetector    │  ← 检测是否需要任务自动化
│ (LLM 分析)      │
└────────┬────────┘
         │ 触发?
    ┌────┴────┐
    │ 否      │ 是
    ▼         ▼
  正常对话   询问用户确认
                 │
                 ▼
          ┌─────────────────┐
          │ TaskPlanner     │  ← LLM 生成执行计划
          │ (复用现有)       │
          └────────┬────────┘
                   ▼
          ┌─────────────────┐
          │ TaskPanel (UI)  │  ← 独立任务面板
          │ + TaskExecutor  │  ← 后台执行
          └─────────────────┘
```

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

## 四、数据模型

### 4.1 数据库表：tasks

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending/confirmed/running/paused/completed/failed
    current_step INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    error_message TEXT
);

CREATE TABLE task_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    step_order INTEGER NOT NULL,
    description TEXT NOT NULL,
    command TEXT,
    status TEXT DEFAULT 'pending',  -- pending/running/completed/skipped/failed
    result TEXT,
    error TEXT,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

### 4.2 WebSocket 消息

```typescript
// 服务端 → 客户端
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

## 五、API 设计

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

## 六、流程图

### 6.1 任务创建流程

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

### 6.2 前端交互流程

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

## 七、开发任务分解

### Phase 1: 后端核心
1. 新增 `tasks` / `task_steps` 数据库表
2. 新增 `api/tasks.py` 路由
3. 增强 `TaskExecutor` 支持异步 + 状态持久化
4. WebSocket 推送任务状态

### Phase 2: 前端核心
1. 新增 `/tasks` 路由和 `TasksView.vue`
2. 实现 `TaskPanel.vue` 组件
3. 实现 `TaskCard.vue` 组件
4. 实现危险操作确认弹窗

### Phase 3: 集成
1. TaskDetector 集成到 Agent
2. 完善错误处理
3. 测试全流程

## 八、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 执行时间过长 | 用户等待焦虑 | 显示预估时间 + 实时进度 |
| 危险命令误执行 | 数据丢失 | 双确认机制 + 黑名单 |
| 执行失败 | 任务状态不一致 | 完整的状态机 + 回滚机制 |
| WebSocket 断开 | 状态更新丢失 | 轮询兜底 + 状态持久化 |

## 九、非目标（明确）

- 不做全自动化执行（用户必须确认）
- 不做任务依赖图
- 不做定时任务调度
- 不做任务模板库

---

*文档版本: v1.2*
*日期: 2026-05-09*
*更新: PDCA 循环 + TaskWorkspace 机制（默认本地，自动初始化 git 仓库）*
