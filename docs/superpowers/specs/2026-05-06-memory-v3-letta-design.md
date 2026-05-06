# 记忆系统 V3（Letta 混合模式）设计文档

**日期：** 2026-05-06
**状态：** Draft（待 review）
**目标：** 让 Agent 真正记得住、能自我进化、能从在线资料中沉淀知识

## 1. 背景与问题

当前记忆系统（V2）存在 5 个核心缺陷：

| 问题 | 现状 |
|------|------|
| 只有 ADD，无 UPDATE/DELETE | 提取后只做去重保存，旧记忆永远不会被修正 |
| 没有遗忘机制 | 记忆只增不减，召回噪声越来越大 |
| 没有整合压缩 | 碎片化记忆堆积（"喜欢 Python""用 Python 写后端"分两条） |
| 提取粒度粗 | 只能从单轮对话提取，长对话上下文丢失 |
| 没有自我进化 | 记忆是静态的，Agent 不会主动修改 |

参考项目：
- [Mem0](https://github.com/mem0ai/mem0) — LLM 驱动的 ADD/UPDATE/DELETE/NOOP 决策
- [Letta (MemGPT)](https://github.com/letta-ai/letta) — Agent 自编辑 core memory
- [Ebbinghaus Decay for Agents](https://fazm.ai/blog/ebbinghaus-decay-ai-agent-memory-layer) — 遗忘曲线

V3 采用 **Letta 模式 + 混合编辑触发 + 软衰减 + Web 沉淀**。

## 2. 总体架构

```
┌─────────────────────────────────────────────────────┐
│ System Prompt 注入                                   │
│ ├─ persona             (Agent 人格)                  │
│ ├─ user_profile        (用户画像)                    │
│ ├─ project_context     (项目上下文)                  │
│ └─ working_principles  (协作准则)                    │
└─────────────────────────────────────────────────────┘
                        ▲
                        │ 自主编辑（Agent 调用工具）
                        │ 后处理反思（每轮兜底）
                        │
┌─────────────────────────────────────────────────────┐
│ Core Memory (4 块固定区块)                            │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Archival Memory (无限条，embedding + 衰减)            │
└─────────────────────────────────────────────────────┘
   ▲                              ▲
   │ 检索（衰减加权排序）           │ 写入
   │                              │
   └─→ RAG 注入 system prompt      │
                                  │
   ┌──────────────────────────────┤
   │  后处理反思 LLM（每轮对话后异步） │
   │  - 决定 core memory 更新       │
   │  - 决定 archival 写入          │
   └──────────────────────────────┤
                                  │
   ┌──────────────────────────────┤
   │  Web 工具搜索结果              │
   │  → 反思识别"新知识" → archival │
   │  source="web"                 │
   └──────────────────────────────┘
```

## 3. 组件设计

### 3.1 Core Memory（4 块固定区块）

| 块名 | 内容 | 大小上限 | 何时更新 |
|------|------|---------|---------|
| `persona` | TARS 的人格定位、口吻、工作方式 | 2KB | 用户反馈风格偏好时 |
| `user_profile` | 用户身份/角色/技术栈/偏好 | 2KB | 对话中学到新用户信息时 |
| `project_context` | 当前项目目标/约束/进展 | 2KB | 项目状态变化时 |
| `working_principles` | 协作准则累积（如"不要主动改文档"） | 2KB | 收到明确反馈规则时 |

**初始内容：** 启动时若 4 行不存在，写入预设默认值（如 persona 默认为"TARS：理性、简洁、注重证据的工程助手"）。

**超长 trim 策略：** 内容超过 2KB 时，从开头删除最旧的行直到落在 2KB 内（保留最新内容）。每行视为以 `\n` 分隔的独立条目。

**System Prompt 注入格式：**
```
## 核心记忆

### Persona
{persona 内容}

### User Profile
{user_profile 内容}

### Project Context
{project_context 内容}

### Working Principles
{working_principles 内容}
```

### 3.2 Archival Memory（长期记忆）

字段（在现有 `memories` 表上扩展）：
- `id`, `content`, `category`, `importance`, `embedding`, `created_at`
- **新增** `last_accessed` (timestamp，已存在但未充分利用)
- **新增** `access_count` (int，每次被召回 +1)
- **新增** `source` (text: `conversation` | `web` | `manual`)

`category` 取值：`fact` / `preference` / `decision` / `domain_knowledge`。

### 3.3 记忆工具（暴露给 Agent，混合模式的"自主"半边）

```
core_memory_append(block: str, content: str)
  → 追加到指定 core memory 块（自动 trim 到 2KB）

core_memory_replace(block: str, old: str, new: str)
  → 替换指定块中的某段文本

archival_insert(content: str, category: str, importance: float)
  → 写入长期记忆

archival_search(query: str, limit: int = 5)
  → 检索长期记忆（已经在 system prompt 自动注入，但 Agent 可显式调用获取更多）
```

工具注册到现有 `ToolRegistry`，参数 schema 标准化为 JSON Schema。

### 3.4 后处理反思（混合模式的"兜底"半边）

**触发：** 每轮对话结束后，异步（不阻塞响应返回给用户）调用一次反思 LLM。

**输入：**
- 当轮 user message + assistant response
- 当前 4 块 core memory 的快照

**Prompt 模板：**
```
你是记忆管理助手。基于本轮对话，判断需要做的记忆操作。

当前 core memory：
- persona: {...}
- user_profile: {...}
- project_context: {...}
- working_principles: {...}

本轮对话：
User: {user_msg}
Assistant: {assistant_msg}

输出 JSON 数组，每个元素是一个操作：
[
  {"op": "update_core", "block": "user_profile", "action": "append|replace",
   "old": "...", "new": "..."},
  {"op": "archive", "content": "...", "category": "fact|preference|decision|domain_knowledge",
   "importance": 0.0-1.0, "source": "conversation"},
  {"op": "noop"}
]

规则：
- 用户明确反馈的协作准则 → working_principles
- 用户身份/技术栈/偏好 → user_profile
- 项目目标/进展变化 → project_context
- 风格反馈 → persona
- 一次性事实/对话片段 → archive 到 archival memory
- 无明显新信息 → noop
```

**执行：** 解析输出，按 op 类型分发到 `CoreMemoryManager` 或 `ArchivalManager`。失败/超时 → 静默跳过，不影响主流程。使用 `asyncio.create_task()` 确保不阻塞主响应。

**频率控制：** 每轮对话都触发反思。若 LLM 返回 `[{"op": "noop"}]` 则无操作开销极低。不做 N 轮间隔——让 LLM 自己判断是否有新信息。

### 3.5 软衰减检索

**评分公式（Ebbinghaus 衰减）：**

```python
import math
from datetime import datetime, timezone, timedelta

def decay_score(memory, query_similarity: float) -> float:
    now = datetime.now(timezone(timedelta(hours=8)))
    age_hours = (now - memory.last_accessed).total_seconds() / 3600
    # importance 越高衰减越慢；importance=0.5 时半衰期约 30 天（720h）
    half_life = max(memory.importance, 0.1) * 720
    decay = math.exp(-age_hours / half_life)
    return query_similarity * 0.6 + decay * 0.2 + memory.importance * 0.2
```

**强化机制：**
- 命中召回的记忆 → `last_accessed = now`、`access_count += 1`
- `importance` 自动微调：每次被召回 `importance = min(1.0, importance + 0.02)`（被频繁用到的记忆自然变重要）

**不删除：** 衰减分低的自然沉到底部，永不主动删除。用户可手动通过现有 API 删除。

### 3.6 Web 搜索沉淀

不引入新工具，复用现有 `web` 工具。流程：

1. Agent 在对话中调用 `web` 工具
2. 工具结果进入 LLM 上下文
3. **改造点：** 后处理反思的 prompt 中标注"本轮使用了 web 搜索，搜索结果包含的领域知识应优先 archive 为 `category=domain_knowledge`，`source=web`"
4. 下次同类问题，archival_search 优先命中已存知识，不重复搜索

## 4. 数据流

### 4.1 用户消息处理流程（主流程）

```
1. 接收 user message
2. 拉取 4 块 core memory → 注入 system prompt
3. archival_search(user_message) → top 5 注入 system prompt
4. 调用 LLM（携带 4 个记忆工具 + 现有所有工具）
5. ToolDispatcher 多轮处理（包括 LLM 主动调用 core_memory_append 等）
6. 流式返回响应给用户
7. 异步触发 reflector.reflect(conversation, core_memory_snapshot)（不阻塞）
8. reflector 应用所有 op 操作（update_core / archive）
```

### 4.2 反思流程（异步）

```
async def reflect(user_msg, assistant_msg, core_snapshot):
    ops = await llm_call(REFLECTION_PROMPT, ...)
    for op in ops:
        if op.op == "update_core":
            core_manager.apply(op)
        elif op.op == "archive":
            await archival_manager.insert_with_dedup(op)
```

### 4.3 检索流程

```
1. 用 query 算 embedding
2. 取所有 archival 记忆（带 embedding）
3. 对每条算 decay_score(query_sim, age, importance)
4. 排序取 top N
5. 命中的记忆 → last_accessed=now, access_count+=1, importance微调
6. 同时跑 FTS 关键词搜索作为补充
7. 合并去重，按综合分排序
```

## 5. 文件结构

```
backend/tars/memory/
├── __init__.py
├── core_memory.py        (新) CoreMemoryManager + 4 个工具
├── reflector.py          (新) ReflectorLLM
├── decay.py              (新) Ebbinghaus 评分
├── manager.py            (重写) MemoryManager 整合 core + archival + reflector
├── archival.py           (新) ArchivalManager (从 manager.py 拆出来)
├── extractor.py          (保留，仅 reflector 内部使用)
├── deduplicator.py       (保留)
├── embeddings.py         (不变)
└── search.py             (改造) 集成 decay 评分
```

数据库迁移：
- 新表 `core_memory_blocks(name TEXT PRIMARY KEY, content TEXT, updated_at TEXT)`
- `memories` 表新增列：`access_count INTEGER DEFAULT 0`、`source TEXT DEFAULT 'conversation'`
- 启动时自动迁移（`ALTER TABLE` 加列，`INSERT OR IGNORE` 4 个默认 core block）

## 6. 测试计划

测试文件 `backend/tests/test_memory_v3.py`，覆盖：

**Core memory：**
- 启动时 4 块默认值正确写入
- `core_memory_append` 工具调用后内容正确累加
- `core_memory_replace` 替换后内容正确
- 超过 2KB 时自动 trim（保留最新内容）
- System prompt 注入格式正确

**Archival memory：**
- `archival_insert` 写入成功，带 embedding
- 重复内容被 deduplicator 拦截
- `source=web` 字段正确保存

**衰减评分：**
- 时间越近分数越高
- importance 越高衰减越慢
- 命中召回后 `last_accessed` 更新、`access_count` +1、`importance` 微增

**反思器：**
- 解析 LLM 输出 JSON 操作数组
- 解析失败时静默跳过
- 各种 op 类型分发到正确的 manager

**集成：**
- 完整对话流：用户说"我喜欢用 Python 写后端" → 反思后 user_profile 更新
- 用户反馈"以后不要主动改文档" → working_principles 更新
- 调用 web 工具后，反思将搜索结果写入 archival 且 source=web
- 下轮相同问题先命中 archival，不再重复搜索

## 7. 兼容性 / 迁移

- 现有 `memories` 表数据不丢失，自动加列
- 现有 `MemoryManager.extract_and_save()` API 保留，内部改为调用新 reflector
- 现有 `MemoryManager.get_context_for_query()` API 保留，内部改为新 search + decay
- 前端 `MemoryView` 页面无需改动（继续展示 archival memory），可在后续增加 core memory 编辑入口

## 8. 范围之外（明确不做）

- ❌ 多用户记忆隔离（V3 仍假设单用户）
- ❌ 记忆图谱（GraphRAG 风格）
- ❌ 记忆共享/导出/导入
- ❌ Core memory 块的运行时增删（只能改 4 块固定结构）
- ❌ 主动删除衰减低的记忆（永不删，仅排序靠后）
- ❌ 多语言记忆（默认中英混合，由 embedding 模型处理）

## 9. 成功标准

1. 用户连续 3 次说"以后用 X 风格" → 第 3 次后 working_principles 已包含此规则
2. 用户告诉一次"我用 Mac M1" → 后续提问环境相关问题时，回答自然提及 M1
3. Agent 通过 web 工具学到一个事实 → 第二次提问时不再调用 web，直接答出
4. 100 条记忆下，语义检索 top 5 相关性肉眼判定 > 当前实现
5. 24 小时内记忆数据库无异常增长（验证软衰减不引发死循环）
