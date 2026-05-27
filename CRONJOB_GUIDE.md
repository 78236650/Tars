# TARS 定时任务功能使用文档

> **引入版本：v4.3.0**（`delegate` / `prompt` + `cron_execute`）· **当前平台：v4.3.2** — [VERSION.md](docs/01-项目概览/VERSION.md)

## 概述

TARS 支持完整的定时任务系统，允许用户创建、管理和调度自动化任务。调度器在 backend 启动时从数据库加载启用任务，到期时经 **CronTaskExecutor 注册表** 执行。

## 核心功能

### 1. 定时任务管理

- 创建定时任务（支持 cron 表达式）
- 查询、更新、删除定时任务
- 启用/禁用任务
- 任务执行记录（reminder 另有 `reminder_notifications` 表）

### 2. 任务类型（v4.3.0）

| task_type | 执行器 | 行为 |
|-----------|--------|------|
| `reminder` | `ReminderExecutor` | WS 推送提醒消息；可绑定 `session_id` |
| `delegate` | `DelegateExecutor` | 调用子代理，WS 推送 `cron_delegate_result` |
| `prompt` | `PromptExecutor` | 对指定 session 注入 prompt，跑一轮 Agent，推送 `cron_prompt_complete` |

每次执行写入审计日志：`action=cron_execute`。

## Cron 表达式

基本格式：`分钟 小时 日期 月份 星期`

### 示例

| 表达式 | 说明 |
|--------|------|
| `* * * * *` | 每分钟执行一次 |
| `0 * * * *` | 每小时执行一次 |
| `0 9 * * *` | 每天 9 点执行 |
| `0 9 * * 1` | 每周一 9 点执行 |
| `0 9 1 * *` | 每月 1 号 9 点执行 |

## task_config 配置

### reminder

```json
{
  "message": "记得喝水！",
  "session_id": "可选-绑定聊天会话，否则 broadcast"
}
```

WS 事件：`cron_reminder`

### delegate（v4.3.0）

```json
{
  "subagent_type": "code",
  "task": "review sql in reports table",
  "session_id": "目标聊天 session_id"
}
```

- `subagent_type` 可选；省略时由 `SubAgentManager.delegate_task` 自动路由
- 需要 backend 启动时已注入 `Agent`（`CronRuntime(agent=agent)`）

WS 事件：

```json
{
  "type": "cron_delegate_result",
  "job_id": "...",
  "session_id": "...",
  "subagent_type": "code",
  "task": "...",
  "result": "..."
}
```

### prompt（v4.3.0）

```json
{
  "prompt": "总结今日待办并列出优先级",
  "session_id": "必填-目标聊天 session_id"
}
```

WS 事件：`cron_prompt_complete`（Agent 一轮结束后）

## API 接口

### 创建 reminder 任务

```bash
POST /api/cronjobs
Content-Type: application/json
X-API-Key: <your-key>

{
  "name": "每日提醒",
  "description": "每天提醒喝水",
  "cron": "0 9 * * *",
  "task_type": "reminder",
  "task_config": {
    "message": "记得喝水！",
    "session_id": "your-session-uuid"
  }
}
```

### 创建 delegate 任务

```bash
POST /api/cronjobs
Content-Type: application/json

{
  "name": "每日代码审查",
  "cron": "0 18 * * 1-5",
  "task_type": "delegate",
  "task_config": {
    "subagent_type": "code",
    "task": "检查本周 merged PR 的 SQL 变更风险",
    "session_id": "your-session-uuid"
  }
}
```

### 创建 prompt 任务

```bash
POST /api/cronjobs
Content-Type: application/json

{
  "name": "晨间摘要",
  "cron": "0 9 * * *",
  "task_type": "prompt",
  "task_config": {
    "prompt": "根据最近对话，总结待办事项",
    "session_id": "your-session-uuid"
  }
}
```

### 其他接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/cronjobs` | 任务列表 |
| GET | `/api/cronjobs/{job_id}` | 单个任务 |
| PUT | `/api/cronjobs/{job_id}` | 更新 |
| PUT | `/api/cronjobs/{job_id}/enable?enabled=true` | 启用/禁用 |
| DELETE | `/api/cronjobs/{job_id}` | 删除 |

## Python 示例

```python
import httpx

BASE = "http://localhost:8000"
HEADERS = {"X-API-Key": "your-api-key"}

async def create_delegate_job():
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE}/api/cronjobs",
            headers=HEADERS,
            json={
                "name": "周报子代理",
                "cron": "0 17 * * 5",
                "task_type": "delegate",
                "task_config": {
                    "subagent_type": "writing",
                    "task": "起草本周工作总结",
                    "session_id": "sess-abc",
                },
            },
        )
        print(r.json())

async def create_prompt_job():
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE}/api/cronjobs",
            headers=HEADERS,
            json={
                "name": "晨间 prompt",
                "cron": "0 8 * * *",
                "task_type": "prompt",
                "task_config": {
                    "prompt": "列出今日三个最重要任务",
                    "session_id": "sess-abc",
                },
            },
        )
        print(r.json())
```

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/tars/cron/runtime.py` | CronRuntime + 执行调度 |
| `backend/tars/cron/executors/` | reminder / delegate / prompt 执行器 |
| `backend/tars/tools/builtin/cronjob.py` | Agent 工具入口 |
| `backend/tars/database/base.py` | `cronjobs` 表 |
| `backend/tars/main.py` | REST API |
| `backend/tars/scheduler.py` | 底层调度器 |

## 测试与验收

```bash
# 单元/集成测试
cd backend
python3 -m pytest tests/test_cron_delegate_prompt.py tests/unit/test_cron_runtime.py -q

# Phase 3 完整验收（含 Channels / Approval / Handoff）
./scripts/acceptance/phase3-openclaw.sh
```

## 启动服务

```bash
cd backend
python -m uvicorn tars.main:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后调度器自动 `load_from_db()` 并注册到期任务。

## 相关文档

- [Channels 架构](docs/04-运维文档/channels-architecture.md)
- [OpenClaw Phase 3 设计](docs/superpowers/specs/2026-05-24-openclaw-phase3-design.md)

---

*平台文档对齐: TARS v4.3.2 · 见 [VERSION.md](docs/01-项目概览/VERSION.md) · 更新: 2026-05-26*
