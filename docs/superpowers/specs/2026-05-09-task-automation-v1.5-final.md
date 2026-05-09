# 任务自动化设计（v2.4）— v1.5 最终版

- **日期**：2026-05-09
- **版本**：v1.5.1（Kiro 整合 + DeepSeek TUI 终审 + Kiro 微调）
- **状态**：定稿，可进入实施
- **上游版本**：v1.2（原始）→ v1.3（DeepSeek 6 项修正）→ v1.4（Kiro 3 项补强）→ v1.5（4 开放问题归档）→ v1.5.1（触发三档 + workspace 兜底警示）
- **本版增量**：解决 4 个开放问题 + 明确实施路径

## v1.4 → v1.5 → v1.5.1 变更

| # | 问题 | v1.4 状态 | v1.5 决定 | v1.5.1 微调 |
|---|------|----------|----------|------------|
| 1 | TaskDetector 重复判断 | 关键词→注入提示→LLM 再判 | 关键词命中直通 | **三档**：`/plan` + 无疑问词 → 硬指令；含疑问词 → 软提示 |
| 2 | WebSocket 推送路径 | 未指定通道 | 复用 `Channel.send()` | 同 v1.5 |
| 3 | `get_session_workspace` 不存在 | open question | `Path(__file__)` 兜底 | **保留方案，加警示**：兜底指向 TARS 仓库根，非用户项目；首次任务强制用户确认 |
| 4 | `expected_artifacts` 成本 | open question | 可选字段 | 同 v1.5 |

---

# 以下为完整正文

## 一、背景与目标

### 1.1 现状（v2.3）

| 组件 | 文件 | 已实现 |
|------|------|--------|
| TaskPlannerTool | `orchestration/planner.py` | LLM tool call 提交计划 |
| TaskExecutor | `orchestration/executor.py` | 重试(2次) + 占位符替换 + abort/skip + WS 推送 |
| TaskPlan/TaskStep | `orchestration/models.py` | dataclass（内存） |
| Channel.send() | `channels/` | WebSocket 消息推送 |

**已实现的不重做。** 本设计仅做增量。

### 1.2 增量目标

1. **TaskDetector**：关键词 + `/plan` 命令 → 自动触发规划，不绕 LLM 二判
2. **StepVerifier（Check）**：6 种验证类型，每步执行后自动校验
3. **状态持久化**：SQLite `tasks` / `task_steps` 表，崩溃可恢复
4. **产出可视**：artifacts + output_summary 前端展示
5. **Act 升级**：重试×3 → 跳过 → 中止 结构化决策
6. **ChatView 抽屉**：右侧滑出 TaskPanel，响应式三档断点

### 1.3 非目标

- 不做全自动执行（用户必须确认）
- 不做任务依赖图 / 定时调度 / 任务模板库 / 跨系统工作流

## 二、PDCA 执行模型

| 阶段 | 增量实现 |
|------|---------|
| Plan | TaskDetector（新）+ TaskPlannerTool（已有） |
| Do | TaskExecutor（已有，复用) |
| Check | **StepVerifier（新）**：6 种 verify 类型 |
| Act | 重试×3（指数退避）→ 跳过 → 中止（升级已有逻辑） |

### 2.1 步骤验证类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `exit_code` | 退出码 | `expected: 0` |
| `output_contains` | 输出含关键字 | `expected: "success"` |
| `output_not_contains` | 输出不含错误 | `expected: "error"` |
| `file_exists` | 文件存在 | `expected: "dist/index.html"` |
| `file_not_exists` | 文件不存在 | 清理后检查 |
| `custom` | LLM 判断 | 复杂语义 |

缺省 verify → 默认 `exit_code == 0`。

## 三、总体架构

```
用户消息 ──┬──► /plan 命令（CommandParser 拦截）
          │
          └──► TaskDetector（关键词 + 疑问词判别）
                   │ mode
             ┌─────┼─────┐
           NONE  SOFT    HARD
             │    │       │
          正常 LLM自判   硬指令注入
           主  是否调   "请调 task_planner"
           LLM  tool      │
                │         │
                └─── 主 LLM ───►调 task_planner
                         │
                         ▼
          TaskPlannerTool.execute()（已有）
                   │
          pop_pending_plan() → TaskStateStore.save()（新）
                   │
          Channel.send("task_created") → 前端抽屉滑出
                   │
          TaskExecutor.execute()（已有，增强 Act）
                   │ 每步
          StepVerifier.check()（新）→ Channel.send("step_verified")
                   │
            pass ───── fail ──→ 重试×3 → 询问 → 跳过/中止
                   │
          artifacts 采集 → Channel.send("task_completed")
```

## 四、TaskDetector（v1.5.1 三档版）

### 4.1 触发规则

v1.5 的"关键词命中直通"会误触发询问类消息（"上次 deploy **怎么回事**"/"为什么要做 **release** 管理"）。v1.5.1 加一层疑问词判别，纯规则零 LLM 调用：

```python
TRIGGER_KEYWORDS = ["部署","构建","发布","测试","deploy","build","release","test"]
QUESTION_MARKERS = ["?","？","是什么","为什么","怎么回事","是啥","啥意思",
                    "what","why","how","怎样"]

class TriggerMode(str, Enum):
    NONE = "none"    # 不触发
    HARD = "hard"    # 硬指令：强制调 task_planner
    SOFT = "soft"    # 软提示：LLM 自判是否调

def detect_task_intent(user_msg: str, is_slash_plan: bool) -> TriggerMode:
    # /plan 命令 → 硬指令（零歧义）
    if is_slash_plan:
        return TriggerMode.HARD

    msg_lower = user_msg.lower()
    has_kw = any(kw in msg_lower for kw in TRIGGER_KEYWORDS)
    if not has_kw or len(user_msg) <= 50:
        return TriggerMode.NONE

    # 含疑问词 → 软提示；否则 → 硬指令
    has_question = any(q in msg_lower for q in QUESTION_MARKERS)
    return TriggerMode.SOFT if has_question else TriggerMode.HARD
```

### 4.2 命中后行为

| 模式 | 行为 |
|---|---|
| `NONE` | 什么都不做，消息正常进主 LLM |
| `SOFT` | system prompt 注入：`"检测到可能的任务意图。若用户确实需要多步骤执行，可调用 task_planner 工具。"` |
| `HARD` | system prompt 注入：`"检测到任务意图。请调用 task_planner 工具为以下任务制定执行计划：{user_msg}"` |

### 4.3 与 Scene Analyzer 的关系

- v2.2 Scene Analyzer 上线后：`intent ∈ planning.*` 可作为**额外触发源**（与关键词等效）
- `planning.explain` 类意图走 SOFT 而非 HARD，防止"解释一下部署流程"被误当执行
- v2.2 未上线：走本节 4.1 关键词方案
- **本设计不依赖 v2.2 上线**

## 五、Workspace 上下文（v1.5.1 加警示）

### 5.1 路径解析 4 级优先级

```python
def resolve_workspace_path(session_id, api_override=None):
    # 1. API 显式传入
    if api_override and Path(api_override).exists():
        return api_override, "api"

    # 2. Workspace Manager（若接口已实现）
    ws = workspace_manager.get_session_workspace(session_id)
    if ws:
        return ws, "workspace_manager"

    # 3. TARS 仓库根目录兜底
    #    警示：这是 TARS 自己的仓库根，不是用户的目标项目。
    #    只用于防 crash；命中时必须强标识 + 前端二次确认。
    project_root = Path(__file__).resolve().parent.parent.parent
    if project_root.exists() and (project_root / ".git").exists():
        return str(project_root), "tars_repo_root"

    # 4. ~/.tars/workspaces/{slug}/
    slug = f"{datetime.now():%Y%m%d_%H%M%S}_{title_to_slug(title)}"
    path = Path.home() / ".tars" / "workspaces" / slug
    path.mkdir(parents=True, exist_ok=True)
    if not (path / ".git").exists():
        run(["git", "init"], cwd=path)
    return str(path), "tars_fallback"
```

### 5.2 前端确认强化（v1.5.1 新增）

不同 `workspace_source` 的前端展示策略：

| source | 展示 | 首次任务确认 |
|---|---|---|
| `api` | 绿色标签"用户指定" | 否（用户已明示） |
| `workspace_manager` | 绿色标签"当前项目" | 否 |
| `tars_repo_root` | **黄色警告标签"TARS 仓库根（请确认）"** | **必须确认** |
| `tars_fallback` | 蓝色标签"临时工作区" | 否（安全隔离） |

任务创建时 session 级别缓存"已确认的 workspace"——同一 session 内后续任务沿用，不重复弹窗。

## 六、数据持久化

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL, title TEXT NOT NULL, goal TEXT NOT NULL,
    workspace_path TEXT NOT NULL, workspace_source TEXT NOT NULL,
    status TEXT DEFAULT "pending",
    current_step INTEGER DEFAULT 0, total_steps INTEGER DEFAULT 0,
    artifacts TEXT, output_summary TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    completed_at TEXT, error_message TEXT
);

CREATE TABLE task_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    step_order INTEGER NOT NULL,
    description TEXT NOT NULL, tool TEXT NOT NULL, arguments TEXT,
    verify_type TEXT, verify_expected TEXT, verify_msg TEXT,
    expected_artifacts TEXT,
    status TEXT DEFAULT "pending", result TEXT, error TEXT,
    retries INTEGER DEFAULT 0,
    started_at TEXT, completed_at TEXT
);
```

**崩溃恢复**：启动时扫描 `status IN ("running","paused")`，默认置 paused，用户手动恢复。

## 七、产出追踪（v1.5 修正 #4）

`expected_artifacts` 为**可选字段**：
- Planner 可填（如 `["dist/index.html"]`），不强制
- 不填时 executor 仅靠 `git status --porcelain` 自动采集新增/修改文件
- 结果写入 `tasks.artifacts`
- `output_summary` 取最后成功步骤 result 前 200 字符

## 八、Act 策略升级

现有 executor(`max_retries=2`) 升级为：

```
步骤失败 → Check 验证 → 自动重试（最多3次，间隔 [1s,2s,4s]）
  → 仍失败 → 询问用户：[重试] [跳过] [中止]
  → 超时 120s → 默认中止
```

## 九、WebSocket 推送（v1.5 修正 #2）

**复用现有** `Channel.send()` 推送以下事件：

| 事件 | 触发时机 |
|------|---------|
| `task_created` | 计划生成完毕，存入 DB |
| `step_started` | 某步开始执行 |
| `step_verified` | 某步 Check 通过 |
| `step_failed` | 某步失败 |
| `step_retrying` | 重试中 |
| `confirmation_needed` | 危险命令待确认 |
| `task_completed` | 全部步骤完成 |
| `task_aborted` | 用户中止 |

## 十、前端（v1.4 保留）

- **ChatView 右侧抽屉**：360px，点击 Header 任务图标 / 任务创建时滑出
- **响应式三档**：≥1200px 推入 / 900-1199px 悬浮覆盖 / <900px 底部抽屉
- **任务卡片**：步骤列表 + 状态图标 + 耗时 + 产出摘要
- **不新增独立路由**

## 十一、危险操作

- 黑名单：`rm -rf` `mkfs` `dd if=` `> /dev/sd*` `chmod -R 777 /` `kill -9 1`
- high 级：点击确认；**critical 级**：手动输入 "yes"
- 超时 300s 未响应 → 默认中止

## 十二、API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/tasks/` | GET | 列出当前 session 任务 |
| `/api/tasks/` | POST | 创建任务 |
| `/api/tasks/{id}` | GET | 任务详情 |
| `/api/tasks/{id}/confirm` | POST | 确认危险操作 |
| `/api/tasks/{id}/pause` | POST | 暂停 |
| `/api/tasks/{id}/resume` | POST | 恢复 |
| `/api/tasks/{id}/cancel` | POST | 取消 |
| `/api/tasks/{id}/retry` | POST | 重试 |

## 十三、分期上线

| 期 | 时长 | 范围 |
|----|------|------|
| 一期 | 4-5d | TaskDetector + Workspace 解析 + SQLite + API |
| 二期 | 3-4d | StepVerifier(6种) + Act 升级 + artifacts |
| 三期 | 3-4d | 前端抽屉 + 响应式 + 危险弹窗 |
| 四期 | 2d | /plan 联调 + 端到端测试 + 文档 |

总计 ≈ 2-2.5 周。

## 十四、风险

| 风险 | 缓解 |
|------|------|
| Workspace 解析错 | 4 级优先级 + 前端展示 workspace_source 供确认 |
| 关键词误触发 | 长度>50 过滤 + 用户可 `/no-plan` 禁用 |
| 重试掩盖真 bug | 前端展示 retries 计数 >0 时黄色标识 |
| artifacts 污染 | 只采集任务开始后的变更 |
| 崩溃续跑危险命令 | 默认 paused + 危险步骤重走双确认 |

## 十五、版本速查

| 议题 | v1.2 | v1.3 | v1.4 | v1.5 | v1.5.1 |
|------|------|------|------|------|--------|
| 触发 | LLM 判断 | 关键词+长度 | 同 v1.3 | 直通 | **三档（疑问词判别）** |
| Workspace | ~/.tars/ | os.getcwd()⚠️ | WM 三级 | TARS 根兜底 | **兜底+前端强确认** |
| 验证 | ✅ 6种 | 未提 | ✅ 保留 | 同 v1.4 | 同 v1.5 |
| 推送 | 未指定 | 未指定 | 未指定 | **复用 Channel.send()** | 同 v1.5 |
| artifacts | 未提 | 新增字段 | 双层来源 | **可选字段** | 同 v1.5 |
| 前端 | /tasks | 抽屉 | 抽屉+响应式 | 同 v1.4 | **workspace_source 分色标签** |
| 分期 | Phase 1-3 | 未分期 | 4期 | 同 v1.4 | 同 v1.5 |

---

*文档版本: v1.5.1 最终版*
*审阅链: 用户(v1.2) → DeepSeek TUI(v1.3) → Kiro(v1.4) → DeepSeek TUI 终审(v1.5) → Kiro 微调(v1.5.1)*
*日期: 2026-05-09*
*状态: 定稿，可进入实施*