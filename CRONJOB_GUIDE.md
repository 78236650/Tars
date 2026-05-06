# TARS 定时任务功能使用文档

> **版本：v2.0.0**（定时任务功能从 v1.0 延续至今，接口不变）

## 概述

TARS 支持完整的定时任务系统，允许用户创建、管理和调度自动化任务。

## 核心功能

### 1. 定时任务管理

- 创建定时任务（支持 cron 表达式）
- 查询、更新、删除定时任务
- 启用/禁用任务
- 任务执行记录

### 2. 任务类型

- **reminder**: 提醒任务
- **delegate**: 子代理任务
- **prompt**: 自动执行提示词

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

## API 接口

### 创建定时任务

```bash
POST /api/cronjobs
Content-Type: application/json

{
    "name": "每日提醒",
    "description": "每天提醒喝水",
    "cron": "0 9 * * *",
    "task_type": "reminder",
    "task_config": {
        "message": "记得喝水！"
    }
}
```

### 获取任务列表

```bash
GET /api/cronjobs
```

### 获取单个任务

```bash
GET /api/cronjobs/{job_id}
```

### 更新任务

```bash
PUT /api/cronjobs/{job_id}
Content-Type: application/json

{
    "name": "新名称",
    "cron": "0 8 * * *"
}
```

### 启用/禁用任务

```bash
PUT /api/cronjobs/{job_id}/enable?enabled=true
```

### 删除任务

```bash
DELETE /api/cronjobs/{job_id}
```

## 使用示例

### Python 示例

```python
import httpx
import json

BASE_URL = "http://localhost:8000"

# 创建任务
async def create_cronjob():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/cronjobs",
            json={
                "name": "每日提醒",
                "description": "每天提醒喝水",
                "cron": "0 9 * * *",
                "task_type": "reminder",
                "task_config": {"message": "记得喝水！"}
            }
        )
        print(response.json())

# 获取任务
async def get_cronjobs():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/cronjobs")
        print(response.json())
```

### 前端示例

```javascript
// 创建任务
async function createCronJob() {
    const response = await fetch('/api/cronjobs', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            name: '每日提醒',
            cron: '0 9 * * *',
            task_type: 'reminder',
            task_config: {
                message: '记得喝水！'
            }
        }),
    });
    return await response.json();
}

// 获取任务列表
async function getCronJobs() {
    const response = await fetch('/api/cronjobs');
    return await response.json();
}
```

## 数据库表结构

### cronjobs

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT | 任务 ID (主键) |
| user_id | TEXT | 用户 ID |
| name | TEXT | 任务名称 |
| description | TEXT | 任务描述 |
| cron_expression | TEXT | cron 表达式 |
| task_type | TEXT | 任务类型 |
| task_config | TEXT | 任务配置 (JSON) |
| enabled | INTEGER | 是否启用 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |
| last_run | TIMESTAMP | 上次执行时间 |
| next_run | TIMESTAMP | 下次执行时间 |

## 相关文件

| 文件 | 说明 |
|------|------|
| `tars/database/base.py` | 数据库操作 (包含 CronJob 类) |
| `tars/scheduler.py` | 任务调度器 |
| `tars/execution/cronjob.py` | 定时任务工具 |
| `tars/main.py` | API 接口定义 |

## 测试

运行测试脚本：
```bash
python test_cronjob.py
```

## 启动服务

```bash
cd backend
python -m uvicorn tars.main:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后，调度器将自动启动并管理定时任务！
