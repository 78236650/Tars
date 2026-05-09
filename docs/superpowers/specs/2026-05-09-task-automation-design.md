# 任务自动化设计（E1）

- **日期**：2026-05-09
- **版本**：v1.0
- **状态**：草稿

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

## 二、总体架构

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

## 三、核心组件

### 3.1 TaskDetector

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

### 3.2 TaskPanel（前端）

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

### 3.3 TaskExecutor（增强）

**复用现有**：`backend/tars/orchestration/executor.py`

**增强点**：
1. **异步执行**：不阻塞主对话
2. **状态持久化**：任务状态存入数据库
3. **WebSocket 推送**：实时更新前端面板
4. **危险操作拦截**：危险命令执行前暂停，等待用户确认

### 3.4 危险操作处理

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

*文档版本: v1.0*
*日期: 2026-05-09*
