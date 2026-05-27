---
doc_type: spec
status: superseded
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# 任务自动化设计（v2.4）— v1.4 整合版

- **日期**：2026-05-09
- **版本**：v1.4（Kiro 评审 + 补强）
- **状态**：草稿
- **上游版本**：
  - v1.2（原始 `task-automation-design-original.md`）
  - v1.3（DeepSeek 审阅 `task-automation-v2.4-design.md`）
- **本版性质**：基于 v1.3 的 6 项修正，补强 3 处漏洞 + 保留 v1.2 的 1 处被忽视价值点

## 相对 v1.3 的调整决策

| # | v1.3 修正 | v1.4 判定 | 补强点 |
|---|---|---|---|
| 1 | TaskDetector 改显式触发 | ✅ 采纳 | 明确 `/plan` 绕过长度判断 |
| 2 | Workspace 改项目根目录 | ⚠️ **有漏洞** | `os.getcwd()` 是后端启动目录，不是用户项目；改从 Workspace Manager 读 |
| 3 | 产出摘要字段 | ✅ 采纳 | 补清 `artifacts` 的数据来源（自动抽取 + planner 预声明） |
| 4 | 明确 Plan+Check+Act 增量 | ✅ 采纳 | **保留 v1.2 的步骤验证机制**（v1.3 修正摘要未提，不能被一起砍） |
| 5 | /plan 与自动触发共享 TaskPlanner | ✅ 采纳 | 明确共享到 `TaskPlannerTool` 实例 + `pop_pending_plan()` |
| 6 | 前端改抽屉 | ✅ 采纳 | 补响应式小屏方案 |

## 相对 v1.2 的保留

- **步骤验证机制**（verify.type: exit_code / output_contains / file_exists / ...）—— 这是 v1.2 核心新增价值，v1.3 修正摘要未提，本版明确保留并细化
- **TaskWorkspace 目录结构** —— 作为第三优先级 fallback 保留
- **危险命令黑名单 + 双确认** —— 保留
- **WebSocket 推送 + 暂停/恢复/取消 API** —— 保留

## 相对 v1.2/v1.3 的删减

- 不再做"LLM 判断多步骤意图"自动触发（与 Scene Analyzer 意图识别重叠）
- 不再新增独立 `/tasks` 路由（改为 ChatView 内嵌抽屉）
- 不再让 TaskExecutor 重做重试/占位符/失败决策（现有 `orchestration/executor.py` 已实现，仅做状态持久化增量）

---

## 一、背景与目标

### 1.1 现状

TARS v2.3 已有：

| 组件 | 文件 | 已实现 |
|---|---|---|
| TaskPlannerTool | `orchestration/planner.py` | LLM 通过 tool call 提交计划 |
| TaskExecutor | `orchestration/executor.py` | 重试（2 次）+ 占位符替换 + 失败决策（abort/skip）+ WebSocket 推送 |
| TaskPlan/TaskStep | `orchestration/models.py` | dataclass 数据模型（内存） |

**已实现的功能不要重做**。本设计仅做增量。

### 1.2 目标（增量）

1. **自动触发入口**：识别用户的多步骤意图，主动询问是否启动规划
2. **步骤验证（Check）**：每步执行后自动验证结果，不盲信退出码
3. **状态持久化**：任务进度写 SQLite，支持崩溃恢复
4. **产出可视**：任务完成后展示产生的文件和关键输出
5. **统一入口**：`/plan` 命令与自动触发共享同一 Planner 实例
6. **前端抽屉**：ChatView 内嵌任务面板，不占独立路由

### 1.3 非目标

- 不做全自动执行（始终需要用户确认）
- 不做任务依赖图解析
- 不做定时调度
- 不做任务模板库
- 不做跨系统工作流

## 二、理论基础：PDCA 循环

| 阶段 | 含义 | 增量实现 |
|---|---|---|
| Plan | 分析问题制定方案 | TaskDetector（新）+ TaskPlannerTool（已有） |
| Do | 按计划执行 | TaskExecutor（已有） |
| Check | 验证结果 | **新增**：6 种验证类型 |
| Act | 根据结果调整 | 已有 abort/skip，升级为 **重试×3 → 跳过 → 中止** 的结构化决策 |

### 2.1 步骤验证机制（Check，v1.2 保留）

每步骤 JSON 增加 `verify` 字段：

```json
{
  "id": 1,
  "description": "git pull 拉取最新代码",
  "tool": "shell",
  "arguments": {"cmd": "git pull origin main"},
  "verify": {
    "type": "exit_code",
    "expected": 0,
    "error_msg": "拉取代码失败"
  },
  "expected_artifacts": []
}
```

**支持的验证类型**：

| 类型 | 说明 | 示例 |
|---|---|---|
| `exit_code` | 检查退出码 | `expected: 0` |
| `output_contains` | 输出包含关键字 | `expected: "Already up to date"` |
| `output_not_contains` | 输出不包含错误 | `expected: "error"` |
| `file_exists` | 文件存在 | `expected: "dist/index.html"` |
| `file_not_exists` | 文件不存在 | 构建前清理 `node_modules` |
| `custom` | 自定义（调 LLM 判断） | 复杂业务语义 |

若 `verify` 缺省 → 默认走 `exit_code == 0`。

## 三、总体架构

```
用户消息 ──┬──► CommandParser（/plan 显式触发）
          │
          └──► TaskDetector（关键词匹配 + 长度过滤）
                   │
                   ▼
          询问"是否需要规划执行"
                   │(用户确认)
                   ▼
          TaskPlannerTool.execute()
                   │
                   ▼
          TaskStateStore.save()    ← 新增：SQLite 持久化
                   │
                   ▼
          TaskExecutor.execute()
                   │(每步)
                   ▼
          StepVerifier.check()     ← 新增：验证
                   │
            ┌──────┴──────┐
          pass           fail
            │             │
            │      ActPolicy：重试×3 → 跳过 → 中止
            ▼             ▼
          下一步       用户决策
                         │
                  pause/resume API
                         │
                         ▼
          artifacts 采集 → 完成卡片展示
```

## 四、TaskDetector

### 4.1 触发规则（v1.4.1 三档版）

```python
TRIGGER_KEYWORDS = ["部署", "构建", "发布", "测试", "deploy", "build", "release", "test"]
QUESTION_MARKERS = ["?", "？", "是什么", "为什么", "怎么回事", "是啥", "啥意思", "what", "why", "how"]

class TriggerMode(str, Enum):
    NONE = "none"           # 不触发
    HARD = "hard"           # 硬指令：强制调用 task_planner
    SOFT = "soft"           # 软提示：让主 LLM 自判是否调

def detect_task_intent(user_msg: str, is_slash_plan: bool) -> TriggerMode:
    # /plan 命令 → 硬指令（零歧义）
    if is_slash_plan:
        return TriggerMode.HARD

    msg_lower = user_msg.lower()
    has_kw = any(kw in msg_lower for kw in TRIGGER_KEYWORDS)
    if not has_kw or len(user_msg) <= 50:
        return TriggerMode.NONE

    # 关键词命中 + 长度达标
    # 含疑问词 → 软提示（可能是询问而非执行意图）
    # 不含疑问词 → 硬指令（明确的执行意图）
    has_question = any(q in msg_lower for q in QUESTION_MARKERS)
    return TriggerMode.SOFT if has_question else TriggerMode.HARD
```

**设计理由**：v1.4 初版的"一律软提示"多了一轮 LLM 不确定判断；但"一律硬指令"会误触发"上次 deploy **怎么回事**"这类询问。三档方案用疑问词作为判别——零 LLM 额外调用，规则纯确定。

### 4.2 触发时机与注入

在 Agent 主循环、CommandParser 之后、主 LLM 之前调用：

| 模式 | 行为 |
|---|---|
| `NONE` | 什么都不做，消息正常进主 LLM |
| `SOFT` | 在 system prompt 注入：`"检测到可能的任务意图。若用户确实需要多步骤执行，可调用 task_planner 工具。"` |
| `HARD` | 在 system prompt 注入：`"用户需要为此任务制定执行计划。请立即调用 task_planner 工具。"` |

主 LLM 调了 `task_planner` → `pop_pending_plan()` 被 Agent 捕获 → 触发 TaskExecutor。

**不采用前端弹确认框直通方案**：理由是会绕过主 LLM 的自然语言理解能力（多轮上下文、话题延续等），并且需要在前端加独立交互流程，复杂度不划算。

### 4.3 与 Scene Analyzer 的关系

v2.2 记忆重做引入了 Scene Analyzer。若 v2.2 已上线：
- Scene Analyzer 的 `intent ∈ planning.*` 可**替代**本节 4.1 的关键词匹配（更准）
- 疑问词判别逻辑保留，防止 `planning.explain` 类意图误触发

**顺序依赖**：本设计**不依赖** v2.2 上线，关键词方案独立可行。

## 五、Workspace 上下文（v1.4 修正 #2）

### 5.1 路径解析优先级（修正 v1.3 的 `os.getcwd()` 漏洞）

```python
def resolve_workspace_path(session_id: str, api_override: Optional[str]) -> tuple[str, str]:
    """
    返回 (path, source)。source ∈ api / workspace_manager / session_default / tars_fallback
    """
    # 1. API 显式传入
    if api_override and Path(api_override).exists():
        return api_override, "api"

    # 2. Workspace Manager 当前会话绑定的项目目录
    ws_path = workspace_manager.get_session_workspace(session_id)
    if ws_path:
        return ws_path, "workspace_manager"

    # 3. 用户配置的默认工作目录
    default = config.get("tasks.default_workspace")
    if default and Path(default).exists():
        return default, "session_default"

    # 4. Fallback：~/.tars/workspaces/{slug}/（v1.2 保留）
    slug = f"{datetime.now():%Y%m%d_%H%M%S}_{title_to_slug(title)}"
    path = Path.home() / ".tars" / "workspaces" / slug
    path.mkdir(parents=True, exist_ok=True)
    if not (path / ".git").exists():
        run(["git", "init"], cwd=path)
    return str(path), "tars_fallback"
```

**关键点**：绝不使用 `os.getcwd()`（那是后端 uvicorn 启动目录，不是用户项目）。

### 5.2 上下文检测

落定 workspace 后，TaskPlanner 调用前检测可用操作：

```python
def detect_workspace_context(workspace_path: str) -> dict:
    return {
        "workspace_path": workspace_path,
        "has_git": is_git_repo(workspace_path),
        "has_remote": bool(get_git_remotes(workspace_path)),
        "build_tools": detect_build_tools(workspace_path),  # npm/pnpm/yarn/pip/poetry/maven/gradle
        "available_ops": [...],  # 基于上面字段推导
    }
```

将 `available_ops` 注入 TaskPlanner 的 prompt，限制 LLM 只生成可执行操作。

### 5.3 Fallback Workspace 目录结构

```
~/.tars/workspaces/20260509_143052_项目部署/
├── .git/                    # 自动初始化
├── task.md                  # 任务描述
├── steps.json              # 执行步骤记录
├── outputs/                 # 产物输出
└── logs/                    # 执行日志
```

## 六、数据持久化（v1.4 增量）

### 6.1 新增表 `tasks` / `task_steps`

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    title TEXT NOT NULL,
    goal TEXT NOT NULL,
    workspace_path TEXT NOT NULL,
    workspace_source TEXT NOT NULL,     -- api/workspace_manager/session_default/tars_fallback
    status TEXT DEFAULT 'pending',      -- pending/confirmed/running/paused/completed/failed/aborted
    current_step INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 0,
    artifacts JSON,                      -- 产出文件路径数组（新增）
    output_summary TEXT,                 -- 最后一步 stdout 前 3 行（新增）
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    error_message TEXT
);

CREATE TABLE task_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    step_order INTEGER NOT NULL,
    description TEXT NOT NULL,
    tool TEXT NOT NULL,
    arguments JSON,
    verify_type TEXT,                    -- exit_code/output_contains/...
    verify_expected TEXT,
    verify_msg TEXT,
    expected_artifacts JSON,             -- planner 声明的预期产物（新增）
    status TEXT DEFAULT 'pending',
    result TEXT,
    error TEXT,
    retries INTEGER DEFAULT 0,
    started_at TEXT,
    completed_at TEXT
);

CREATE INDEX idx_tasks_session ON tasks(session_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_task_steps_task ON task_steps(task_id, step_order);
```

### 6.2 崩溃恢复

启动时扫描 `status IN ('running', 'paused')` 的任务：
- 默认置为 `paused`，推送到前端显示"未完成任务（可恢复）"
- 用户点击恢复 → 从 `current_step` 续跑
- 不自动续跑，避免重启时误执行危险步骤

## 七、产出追踪（v1.4 修正 #3）

### 7.1 `artifacts` 字段的数据来源

两层采集：

**Planner 预声明**：`task_steps.expected_artifacts`（JSON 数组）
- Planner 在生成每步时显式声明该步的预期产物路径
- 例：`["dist/index.html", "dist/bundle.js"]`

**Executor 自动抽取**：
- 步骤执行后扫描 workspace 的 `git status` diff + 指定工具的产物字段
- `file_write` / `file_create` tool 的 arguments 里的 path
- `shell` tool 执行完后 `git status --porcelain` 的新增/修改文件
- 合并去重写入 `tasks.artifacts`

### 7.2 `output_summary` 规则

- 取最后一个成功步骤的 `result` 前 3 行（或 200 字符，取短者）
- 截断尾部追加 `...`
- 空值时用"任务完成，无显式输出"

## 八、Act 策略升级（v1.4 修正 #4）

### 8.1 失败决策（结构化）

现有 executor 的 `max_retries=2` + `abort/skip` 升级为：

```
步骤失败
    │
    ▼
Check 验证失败？
    │是
    ▼
自动重试（最多 3 次，指数退避 1s/2s/4s）
    │仍失败
    ▼
询问用户：[重试] [跳过] [中止]
    │超时 120s
    ▼
默认：中止（现有行为保留）
```

### 8.2 配置项

```yaml
tasks:
  max_retries: 3              # v1.4 从 2 提升到 3
  retry_backoff_seconds: [1, 2, 4]
  user_decision_timeout_s: 120
  default_on_timeout: abort
```

## 九、前端（v1.4 修正 #6）

### 9.1 ChatView 内嵌抽屉

- **位置**：ChatView 右侧滑出
- **宽度**：桌面端 360px
- **触发**：Header 任务图标点击 / 新任务创建时自动滑出
- **隐藏**：无任务或手动关闭
- **不新增独立路由**

### 9.2 响应式（v1.4 补强）

| 屏幕宽度 | 抽屉行为 |
|---|---|
| ≥ 1200px | 右侧推入，ChatView 自适应收窄 |
| 900-1199px | 右侧悬浮覆盖，ChatView 不收窄 |
| < 900px | 底部 2/3 高度抽屉，点击外部关闭 |

### 9.3 任务卡片内容

```
┌────────────────────────────────────┐
│ 🔄 项目部署 #001         进行中      │
├────────────────────────────────────┤
│ Workspace: /Users/x/proj (git)    │
│                                    │
│ ✓ 1. git pull                      │
│ ◐ 2. npm build        [查看日志]   │
│ ○ 3. 部署到服务器                   │
│ ○ 4. 验证部署结果                   │
│                                    │
│ 产物：dist/index.html, dist/bundle.js│
│                                    │
│               [暂停] [取消]         │
└────────────────────────────────────┘
```

完成态额外展示 `output_summary` 和可点击的 `artifacts` 列表。

## 十、/plan 命令与自动触发（v1.4 修正 #5）

### 10.1 共享 TaskPlannerTool 实例

- Agent 单例持有一个 `TaskPlannerTool` 实例
- `/plan xxx` 命令走 CommandParser，拦截后直接构造一条"请为 xxx 制定计划"的消息注入对话
- 主 LLM 收到后调用 `task_planner` tool → 写入该实例的 `_pending_plan`
- Agent 每轮末尾调 `pop_pending_plan()`：有计划则交 TaskExecutor 执行

### 10.2 等价性

两种入口（显式 `/plan` vs 自动触发）的后续流程**完全相同**：都经过 TaskPlannerTool → TaskExecutor → 持久化 → 前端展示。

## 十一、危险操作拦截（v1.2 保留）

### 11.1 黑名单（继承现有 shell 工具）

- `rm -rf`
- `mkfs`
- `dd if=`
- `> /dev/sd*`
- `chmod -R 777 /`
- `kill -9 1`

### 11.2 双确认流程

```
1. Executor 扫描到命令匹配黑名单
2. 步骤状态设 "awaiting_confirmation"
3. WebSocket 推送 confirmation_needed 事件
4. 前端弹窗显示命令详情 + 风险等级
5. high 级：点击"确认" 即可
6. critical 级：需手动输入 "yes" 字符串
7. 超时 300s 未响应 → 默认中止任务
```

## 十二、API 设计

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/tasks/` | GET | 列出当前 session 任务 |
| `/api/tasks/` | POST | 创建任务（可传 workspace_path 覆盖）|
| `/api/tasks/{id}` | GET | 任务详情（含步骤） |
| `/api/tasks/{id}/confirm` | POST | 确认危险操作 |
| `/api/tasks/{id}/pause` | POST | 暂停 |
| `/api/tasks/{id}/resume` | POST | 恢复 |
| `/api/tasks/{id}/cancel` | POST | 取消 |
| `/api/tasks/{id}/retry` | POST | 重试失败任务 |
| `/api/tasks/{id}/steps/{step_id}/logs` | GET | 步骤日志 |

## 十三、WebSocket 消息

```typescript
interface TaskEvent {
  type:
    | 'task_created' | 'task_updated' | 'task_completed' | 'task_aborted'
    | 'step_started' | 'step_verified' | 'step_failed' | 'step_retrying'
    | 'confirmation_needed' | 'artifacts_collected';
  payload: {
    task_id: string;
    step_id?: number;
    [key: string]: any;
  };
}
```

## 十四、分期上线

| 期 | 时长 | 范围 |
|---|---|---|
| 一期 | 4-5 天 | TaskDetector + Workspace 路径解析 + SQLite 持久化 |
| 二期 | 3-4 天 | StepVerifier（6 种 verify 类型）+ Act 策略升级 + artifacts 采集 |
| 三期 | 3-4 天 | 前端抽屉 + 响应式 + 产出卡片 + 危险操作弹窗 |
| 四期 | 2 天 | /plan 共享联调 + 端到端测试 + 文档 |

总计 ≈ 2-2.5 周。

## 十五、风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| Workspace 路径解析错 | 任务跑在错误目录 | v1.4 明确 4 级优先级；每次任务创建时向用户展示 `workspace_source` 供确认 |
| 关键词误触发 | 打断正常对话 | 长度 >50 过滤；主 LLM 自判是否真调 task_planner；用户可 `/no-plan` 本轮禁用 |
| 自动重试掩盖真 bug | 看似成功实际每次都重试 | 前端显式展示 retries 计数；>0 时以黄色标识 |
| artifacts 抽取污染 | git status 含无关改动被标为产物 | 只采集任务开始后发生变化的文件；对 node_modules/dist/.cache 等目录白名单 |
| 崩溃恢复误跑危险命令 | 重启后续跑删除类步骤 | 默认 paused，用户手动恢复；危险步骤需重走双确认 |
| 持久化写入失败 | 状态丢失 | 关键事件双写（SQLite + 内存），SQLite 失败时降级内存 + 日志告警 |

## 十六、开放问题

- Workspace Manager 的 `get_session_workspace` 当前实现是否支持？需要确认
- 崩溃恢复是否对所有工具安全？`file_write` / `shell` 已经执行过一半的情况如何判断
- `expected_artifacts` 由 Planner 生成 LLM 成本是否接受？可作为可选字段

## 十七、版本速查

| 议题 | v1.2（原始） | v1.3（DeepSeek） | v1.4（本版） |
|---|---|---|---|
| 自动触发 | LLM 意图判断 | `/plan` + 关键词 + 长度 | 同 v1.3，明确 `/plan` 绕过长度 |
| Workspace | `~/.tars/workspaces/` | `os.getcwd()` ⚠️ | Workspace Manager → 配置 → fallback |
| 验证机制 | ✅ 6 种 verify 类型 | 未提 | ✅ 保留（明确细节） |
| Check+Act | 模糊 | 明确增量 | 明确增量 + 保留验证 |
| /plan 关系 | 未提 | 共享 planner | 共享 `TaskPlannerTool` 实例 + `pop_pending_plan` |
| 前端 | /tasks 独立路由 | ChatView 抽屉 | 抽屉 + 响应式三档 |
| artifacts | 未提 | 新增字段 | 数据来源两层（planner 预声明 + executor 抽取） |
| 分期 | Phase 1/2/3 | 未分期 | 4 期共 2-2.5 周 |

---

*文档版本: v1.4 整合版*
*作者: Kiro*
*基于: v1.2 原始 + v1.3 DeepSeek 审阅 + Kiro 评审补强*
*日期: 2026-05-09*
