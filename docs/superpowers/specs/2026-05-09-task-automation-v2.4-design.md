# 任务自动化设计（v2.4）

- **日期**：2026-05-09
- **版本**：v1.3（经 DeepSeek TUI 审阅修正）
- **状态**：草稿
- **原始版本**：v1.2（用户初稿）
- **修正项**：6 处架构调整

## 修正摘要

| # | 调整点 | 原设计 | 修正后 | 理由 |
|---|--------|--------|--------|------|
| 1 | TaskDetector 触发条件 | LLM 意图判断 + 关键词 | 仅显式触发（/plan + 4 个关键词） | 避免频繁打断对话 |
| 2 | TaskWorkspace 默认路径 | ~/.tars/workspaces/ | 项目根目录优先，无项目时 fallback | 操作对象是当前项目 |
| 3 | 任务完成展示 | 仅显示步骤状态 | 增加产出摘要（artifacts + output_summary） | 用户需要看到实际产物 |
| 4 | 与现有 TaskExecutor 关系 | "增强"模糊 | 明确增量：Plan(自动触发)+Check(验证)+Act(跳过/中止) | 避免重复开发 |
| 5 | 与 /plan 命令关系 | 未提及 | 平行入口，共享 TaskPlanner | 两种触发方式统一 |
| 6 | 前端路由 | 独立 /tasks 路由 | ChatView 内嵌抽屉（ChatGPT Canvas 风格） | 避免侧栏 5 项拥挤 |

---

## 六项修正详解

### 1. TaskDetector 触发条件

原设计允许 LLM 判断多步骤意图，会导致频繁打断对话。修正后仅使用显式触发：

- `/plan` 命令（用户主动触发）
- 消息包含关键词：`部署` `构建` `发布` `测试` `deploy` `build` `release` `test`
- 且消息长度 > 50 字符（过滤"测试一下"等短消息）

```python
TRIGGER_KEYWORDS = ["部署", "构建", "发布", "测试", "deploy", "build", "release", "test"]
def detect_task_intent(msg: str) -> bool:
    return any(kw in msg.lower() for kw in TRIGGER_KEYWORDS) and len(msg) > 50
```

### 2. TaskWorkspace 路径

三层优先级：
1. 当前项目根目录（默认 `os.getcwd()`）
2. 用户通过 API 指定的目录
3. `~/.tars/workspaces/{slug}/`（fallback，仅当前两者不可用时）

### 3. 任务完成产出展示

tasks 表新增两个字段：
- `artifacts`: JSON 数组，列出生成的输出文件路径
- `output_summary`: 文本，关键输出摘要（最后一步的 stdout 前三行）

前端完成卡片展示产出文件列表和摘要。

### 4. 与现有 TaskExecutor 的增量

现有代码位于 `backend/tars/orchestration/executor.py`，覆盖 Do + 简单重试。
本设计新增：
- **Plan 入口**: TaskDetector（新文件 `detector.py`）
- **Check**: 6 种验证类型，每次执行后自动校验
- **Act**: 结构化失败决策（重试×3 → 跳过 → 中止）
- **状态持久化**: 任务进度写入 SQLite，崩溃可恢复

### 5. 与 /plan 命令的关系

两者共享同一个 TaskPlanner 实例。区别仅在于触发方式：
- `/plan 部署项目` → CommandParser 拦截 → TaskPlanner
- `帮我部署到服务器` → TaskDetector 匹配 → 询问 → TaskPlanner

### 6. 前端：ChatView 内嵌抽屉

不新增独立路由 `/tasks`。TaskPanel 作为 ChatView 的右侧滑出抽屉组件：
- 宽度 360px，点击 Header 任务图标或任务创建时自动滑出
- 步骤列表 + 实时状态推送 + 完成后产出展示
- 无任务时隐藏

---

完整设计见原始文档：`docs/superpowers/specs/2026-05-09-task-automation-v2.4-design.md`

*文档版本: v1.3（修正版）*
*审阅: DeepSeek TUI V4*
*日期: 2026-05-09*