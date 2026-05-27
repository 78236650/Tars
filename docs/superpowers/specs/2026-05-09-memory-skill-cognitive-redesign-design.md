---
doc_type: spec
status: draft
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# 记忆与技能认知架构重做设计（v2.2）

- **日期**：2026-05-09
- **版本**：草案 v1.0
- **范围**：TARS 记忆系统 + 技能触发机制的联合重构
- **目标版本**：v2.2.0
- **替代**：`2026-05-06-memory-v3-letta-design.md`（v3 基础保留，此为其上层扩展）

## 一、背景与目标

### 1.1 现状痛点

v2.1 已实现 Letta 风格的 Core + Archival + Reflector，但用户反馈系统仍"不够聪明、技能触发呆板"，具体表现在四个记忆症状 + 三个技能症状：

记忆：
1. **该想起没想起**：聊过的事下次查不出来，或召回内容与当前话题无关
2. **存了一堆没用的**：闲聊、一次性操作被写入长期记忆
3. **记忆错乱/不进化**：同一实体的信息散落多条，矛盾时不会合并修正
4. **不能连成线**：实体/时间/话题三种连贯全缺

技能：
5. **不自动激活**：用户提需求但相关技能不生效，需手动 `/skill`
6. **没组合/没优先级**：多技能同启时互相冲突无仲裁
7. **技能表达力弱**：只能提供 prompt 或 tool，无法介入对话流程

### 1.2 根本原因

记忆是"条目堆"、技能是"开关"，两者都缺少 **Agent 对当前场景的自我感知**。没有这个感知，该记的记不到要点、该想起的想不起来、该开的技能不知道该开。

### 1.3 目标

- 建立"场景画像 → 记忆分层 → 技能动态路由"的统一认知架构
- 覆盖实体、时间线、会话三种连贯
- 技能能依据场景自动激活、组合、仲裁
- 保证平滑迁移，老数据不丢

### 1.4 非目标

- 不做图神经网络、不做知识图谱推理引擎（B 方向而非 C 方向）
- 不做多用户跨会话记忆共享（单用户 scope 已足够）
- 不实现技能间通信（hooks 之间互发消息），hooks 之间通过共享 `SkillContext` 间接协作

## 二、核心思想

> TARS 在每轮对话前维护一份 **场景画像（Working Context）** —— 包括"在聊什么实体、什么意图、有哪些未完成的事"。记忆系统围绕这份画像分层写入与检索，技能系统围绕这份画像动态激活。

一切改动都是为这份画像服务的：让它存在、准确、可复用。

## 三、总体架构

```
┌──────────────────────────────────────────────────────────────┐
│  用户消息                                                      │
└────────────┬─────────────────────────────────────────────────┘
             ▼
    ┌────────────────┐
    │ Scene Analyzer │  ← 每轮开头调一次小模型
    │ (LLM 路由)     │    输入: 用户消息 + 最近3轮 + WorkingCtx
    └───┬──────────┬─┘    输出: 意图、新实体、话题转移信号
        │          │
        ▼          ▼
┌──────────────┐ ┌──────────────┐
│ MemoryRouter │ │ SkillRouter  │
│              │ │              │
│ 1. 实体图路  │ │ 基于 trigger │
│ 2. 时间线路  │ │ + scene 打分 │
│ 3. 向量路    │ │ 选 top-K     │
│ 4. 关键词路  │ │ 临时激活     │
└──────┬───────┘ └──────┬───────┘
       ▼                ▼
  ┌─────────────────────────────┐
  │ System Prompt 拼装          │
  │  = Core + Working + 检索块  │
  │    + 激活技能 prompt/tool   │
  └──────────────┬──────────────┘
                 ▼
            主 LLM 对话
                 ▼
    ┌────────────────────────────┐
    │ Reflector (后处理, 异步)    │
    │ 分层写入:                   │
    │  - Semantic: 实体/关系     │
    │  - Episodic: 带时间戳事件   │
    │  - Core: 不变画像修正       │
    │  - WorkingCtx 更新         │
    └────────────────────────────┘
```

### 3.1 新增组件

| 组件 | 类型 | 说明 |
|---|---|---|
| Scene Analyzer | 服务 | 每轮调小模型产出场景画像 |
| Working Context | 数据表 | 会话级短期"在聊什么"|
| Semantic Memory | 数据表（entities + relations）| 实体图 |
| Episodic Memory | 现 archival 升级 | 加时间戳语义 |
| MemoryRouter | 服务 | 四路召回 + 融合打分 |
| SkillRouter | 服务 | 每轮动态选技能 |

### 3.2 删减/改造

- 技能不再用 enable 永久注入；enable 变"候选池"，生效由 Router 决定
- Reflector prompt 简化、写入分流
- `HybridSearch` 成为 MemoryRouter 的一路（向量路），不再单独调用

## 四、记忆四层

### 4.1 Working Context（新增，会话级）

**作用**：记录"当前会话在聊什么"，给 MemoryRouter 和 SkillRouter 做输入。每个 `session_id` 一条。

**表 `working_contexts`**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | TEXT PK | 会话 ID |
| `focus_entities` | JSON | 焦点实体 ID 列表，最多 8 个，FIFO |
| `current_intent` | TEXT | Scene Analyzer 输出的意图，如 `coding.debug` |
| `intent_confidence` | REAL | 意图置信度 |
| `open_threads` | JSON | 未结话题 `[{"topic":"...","last_mentioned":"..."}]`，最多 5 条 |
| `active_skills` | JSON | 本轮选中的技能 ID 列表 |
| `last_scene_snapshot` | JSON | 最近一次 Scene Analyzer 完整输出（供复用/降级） |
| `updated_at` | TEXT | ISO8601 |

**寿命**：跟随 session；超过 72h 未活跃或用户 `/clear` 时清理。

### 4.2 Semantic Memory（新增，实体图）

**作用**：记住"谁是谁、什么是什么、它们怎么关联"。"连成线"的关键层。

**表 `entities`**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | 稳定 ID，如 `person:bob`、`project:tars` |
| `type` | TEXT | `person` / `project` / `tech` / `concept` / `org` |
| `name` | TEXT | 显示名 |
| `aliases` | JSON | 别名数组 |
| `attributes` | JSON | 灵活属性袋 |
| `attributes_history` | JSON | 属性变更历史（冲突保留） |
| `importance` | REAL | 继承衰减 |
| `last_accessed` | TEXT | 命中时刷新 |
| `created_at` | TEXT | |

索引：`idx_entities_type`、`idx_entities_name`、`idx_entities_aliases_fts`（FTS5）

**表 `relations`**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INTEGER PK | |
| `from_entity` | TEXT | |
| `to_entity` | TEXT | |
| `predicate` | TEXT | `works_on` / `uses` / `colleague_of` / `part_of` 等 |
| `confidence` | REAL | 0-1 |
| `source_memory_id` | INTEGER NULL | 来源 episodic memory |
| `created_at` | TEXT | |

索引：`idx_relations_from`、`idx_relations_to`、`UNIQUE(from, to, predicate)`

### 4.3 Episodic Memory（升级现 archival）

**作用**：带时间戳的事件流，回答"上次/之前/昨天…"，承载故事线。

**表 `archival_memories` 新增字段**：

| 新字段 | 说明 |
|---|---|
| `event_time` | TEXT，事件发生时间（允许 Reflector 回填"昨天"） |
| `entity_refs` | JSON，关联实体 ID 列表 |
| `supersedes` | INTEGER NULL，指向被修正的旧记忆，实现"进化" |

**写入规则收紧**（对上"存了一堆没用的"）：
- 必须关联 ≥1 个实体，**或**是用户明确决策，**或**是首次域知识
- 闲聊、一次性操作步骤不进 Episodic
- Reflector 产出 `log_episode` 时如缺 `entity_refs` 直接丢弃

### 4.4 Core Memory（瘦身）

**保持 4 块**，职责收窄：只放"不变的"。会变 → Semantic，一次性 → Episodic，会话内 → Working。

Reflector 的 prompt 不再让它"什么都考虑 Core"，按下一节的分流规则写入。

## 五、Scene Analyzer

### 5.1 调用时机

每轮用户消息到达后、主 LLM 生成前，**同步**调用一次。

### 5.2 输入

- 当前用户消息（截断 2k）
- 最近 3 轮对话摘要（由上轮 Reflector 产出，缓存在 Working Context）
- 当前 Working Context

### 5.3 输出（严格 JSON）

```json
{
  "intent": "coding.debug",
  "intent_confidence": 0.9,
  "entities_mentioned": [
    {"id": "project:tars", "type": "project", "name": "TARS", "is_new": false},
    {"id": "concept:websocket", "type": "concept", "name": "WebSocket", "is_new": false}
  ],
  "topic_shift": false,
  "open_thread_refs": ["v2.2 记忆重做"],
  "needs_memory_recall": true,
  "recall_hints": ["WebSocket 持久连接", "wsStore"]
}
```

### 5.4 意图标签体系

扁平、可扩展：
- `coding.{write|debug|review|refactor|explain}`
- `planning.{decompose|estimate|prioritize}`
- `writing.{draft|edit|translate|summarize}`
- `research.{search|compare|learn}`
- `data.{analyze|transform|visualize}`
- `casual`（闲聊，记忆写入进收紧模式）
- `meta`（关于 TARS 自身的提问）
- `unknown`（解析失败兜底）

技能包可在 `skill.yaml` 的 `trigger.intents` 中声明自己响应哪些意图，允许新增自定义意图名。

### 5.5 模型与延迟预算

- 模型：用户可配，默认 `ollama:qwen2.5:3b`；允许填主模型
- 温度 0.1
- 延迟预算：500ms；超过 3s 超时跳过，用上一轮 Working Context
- 缓存：若用户消息语义未变（嵌入相似度 > 0.95）且未发生 topic_shift，复用上轮结果，跳过本轮调用

### 5.6 失败处理

| 失败类型 | 处理 |
|---|---|
| JSON 解析失败 | `intent: unknown`，Router 走保守策略（仅向量路、不激活可选技能） |
| 超时 | 复用上轮 Working Context |
| 模型不可用 | 跳过，全部走向量 + 关键词双路 |

## 六、MemoryRouter

**替代现 `HybridSearch.search()` 单路召回**。

### 6.1 四路并行策略

| 路径 | 输入 | 权重 | 命中上限 |
|---|---|---|---|
| 实体路 | `entities_mentioned` + Working `focus_entities` | 0.4 | 5 条 episodic + 实体属性 + 一跳关系 |
| 时间线路 | 焦点实体 + `event_time desc` | 0.2 | 3 条最近事件 |
| 向量路 | 用户消息 + `recall_hints` 拼接嵌入 | 0.3 | 5 条 |
| 关键词路（FTS） | 用户消息分词 | 0.1 | 3 条 |

### 6.2 融合打分

- 同一记忆被多路命中时得分叠加
- 命中记忆刷新 `last_accessed`（沿用 reinforce 机制）
- 最终按综合分排序取 top 5-8

### 6.3 降级

- `needs_memory_recall=false` → 仅向量路跑最小检索（top 2）或跳过
- `intent: casual` → 跳过 Episodic 检索，只查 Core + Working

### 6.4 注入格式（写入 system prompt）

```
## 相关上下文

### 涉及的实体
- [Bob] 同事，做 Go 后端，在项目 TARS 上
- [项目 TARS] v2.1.0，FastAPI + Vue3

### 最近相关事件
- (2025-11-10) 决定用 Letta 模式重构记忆，分四层
- (2025-11-12) Bob 提议把 SkillHub 改用 GitHub Releases

### 相关知识
- Function Calling 在 qwen3 上原生支持
```

比现有平坦列表 `[fact] xxx` 更结构化，主 LLM 易用。

## 七、SkillRouter

**替代现"enable 永久注入"机制**。

### 7.1 技能 YAML 新增字段

```yaml
trigger:
  intents: ["writing.translate", "writing.draft"]
  entities: ["concept:language"]
  keywords: ["翻译", "translate", "英译中"]
  conditions: "any"                # any | all
priority: 50                         # 0-100，冲突时排序
lifecycle: "per_turn"                # per_turn | sticky | session
```

### 7.2 生命周期

| 值 | 含义 |
|---|---|
| `per_turn` | 默认；本轮激活，下轮 Router 重新决定 |
| `sticky` | 激活后保持到会话结束或 `/skill off` |
| `session` | 会话开启即激活（兼容"我全程要翻译"场景）|

### 7.3 路由流程

```
1. 取当前 scene 的 intent + entities + 用户消息关键词
2. 对每个已 enable 的候选技能打分：
     score = intent_match * 0.5 + entity_match * 0.3 + keyword_match * 0.2
3. 过滤 score < 0.3
4. 按 priority desc、score desc 排序
5. 取 top 3
6. 冲突检测：若多个技能修改同一 persona 块，保留最高 priority
7. 写入 Working Context 的 active_skills
8. 注入它们的 prompt_template；PluginSkill 的 tool 一直在 registry
```

### 7.4 用户手动控制（保留）

- `/skill <id>` → 强制激活为 `sticky`
- `/skill off <id>` → 本轮及后续 Router 不能选它
- `/auto` → 回到自动路由（清除所有强制状态）

### 7.5 分数匹配算法

- `intent_match`：精确匹配 1.0；前缀匹配（如 `writing.*`）0.7；无匹配 0
- `entity_match`：每个匹配实体 0.5，上限 1.0
- `keyword_match`：至少命中一个关键词 1.0，否则 0

### 7.6 技能 Hooks（本期一起实现）

技能可声明三类 hooks（全部选填）：

```yaml
hooks:
  on_activate: "main.py:on_activate"    # Router 首次激活此技能时触发
  pre_llm: "main.py:pre_llm"            # 给主 LLM 前，可改 system prompt / 注入附加上下文 / 追加工具
  post_llm: "main.py:post_llm"          # 主 LLM 回复后，可改回复内容或触发副作用
```

**签名**：
```python
def pre_llm(ctx: SkillContext) -> SkillContext: ...
```

**`SkillContext` 暴露**：
- `working_context`：只读的当前 Working Context 快照
- `messages`：本轮消息列表（可读可改）
- `system_prompt_parts`：system prompt 分块（可追加）
- `tool_registry`：可临时注册/禁用工具（仅本轮生效）
- `set_response_patch(fn)`：注册一个对主 LLM 回复的后处理函数

**安全约束**：
- Hook 函数最长 2s，超时跳过并记日志
- Hook 只能读写自己的 `ctx.skill_state`（技能私有字典，持久化到 Working Context）
- Hook 不允许直接操作数据库或文件系统，必须通过 tool registry
- Hook 抛异常 → 该技能本轮降级为仅 prompt 注入，不中断对话

**落地范围（本期）**：三个 hook 全部实现，提供最小示例技能 `skills/example_hook/`。不实现技能间通信（非目标 §1.4）。

## 八、Reflector 重做

### 8.1 新操作集（扩展）

```json
[
  {"op": "upsert_entity", "id": "person:bob", "type": "person",
   "name": "Bob", "aliases": ["老王"],
   "attributes": {"role": "同事", "stack": ["Go"]},
   "confidence": 0.9},

  {"op": "upsert_relation", "from": "person:bob", "to": "project:tars",
   "predicate": "works_on", "confidence": 0.9},

  {"op": "log_episode", "content": "Bob 提议 SkillHub 改用 GitHub Releases",
   "event_time": "2026-05-08T14:30:00+08:00",
   "entity_refs": ["person:bob", "project:tars"],
   "importance": 0.75, "supersedes": null},

  {"op": "update_core", "block": "user_profile",
   "action": "append", "new": "用户偏好 monorepo 结构"},

  {"op": "forget", "target": "entity|episode|core",
   "id_or_keyword": "..."},

  {"op": "noop"}
]
```

### 8.2 分流规则（写进 prompt，强制）

| 信息 | 去向 |
|---|---|
| 人/项目/技术/概念首次出现 | `upsert_entity` |
| "A 和 B 有关系"首次或变化 | `upsert_relation` |
| 带时间/决策/关联实体的事件 | `log_episode` |
| 用户不变偏好/技术栈/协作准则 | `update_core`（限 user_profile / working_principles / persona） |
| 过期 core 行 / 过时 episode / 错误 entity | `forget` |
| 无新信息 | `noop` |

**硬约束**：
- `log_episode` 必须带 `entity_refs`（≥1），否则丢弃
- 同内容 24h 内 upsert ≥3 次且 `importance<0.5` → 标"琐碎"，7 天不出现在检索结果
- `update_core` 不允许动 `project_context`（改由 Semantic 承载）

### 8.3 冲突解决

`upsert_entity` / `upsert_relation` 带 `confidence`：
- 高置信度覆盖低置信度
- 属性合并：新属性追加，同名属性新值生效，旧值进 `attributes_history`
- 矛盾属性（如 `role` 从"同事"变"前同事"）保留历史不直接丢

### 8.4 异步 + 批处理

- Reflector 改为丢任务进异步队列，不阻塞对话返回
- 队列每 30s 或积压 5 条触发批量
- 失败重试 2 次，最终失败入死信表（前端可查）
- 保留紧急写入通道见 §8.5

### 8.5 紧急写入通道

**触发语义**：用户在对话中明确要求记住某条信息时（"记住我是左撇子"、"这条要记住"、"以后你要知道 X 是 Y"），主 LLM 应**立即同步**调用以下工具之一，不走 Reflector 队列：

- `core_memory_append(block, content)` —— 同步写 Core Memory，立即生效；适合不变偏好/画像
- `archival_insert(content, category, importance=0.9, entity_refs=[...])` —— 同步写 Episodic；适合具体事件或带实体的事实

**工具描述要点**（注册到 ToolRegistry 时写进 description）：
- "用户**明确**要求记住 / 强调"这条必须记住"时调用。自动反思器已覆盖一般信息，不要为普通陈述反复调用此工具。"
- 主 LLM 调用此工具后应在回复里明确告知用户"已记住 X"，形成反馈闭环

**Reflector 去重**：异步 Reflector 在处理该轮对话时，若发现本轮主 LLM 已通过紧急通道写入某条信息（通过本轮 tool_calls 日志判断），则跳过该条，避免重复写入。

现有两个工具保留，并按上述原则升级其 description。

## 九、数据迁移与兼容

### 9.1 SQLite 迁移脚本（启动时检测 schema_version 自动执行）

```
step 1: 读现 archival_memories
step 2: 回填 LLM 批处理（可后台跑）：
          input: content + category + created_at
          output: entity_refs, event_time≈created_at, 保留 importance
step 3: 新建 entities / relations / working_contexts 表
step 4: 对每条 archival 按回填 entity_refs 反向 upsert：
          首次出现实体生成 entity
          多条共享的实体自动建立弱关系（confidence=0.3）
step 5: Core memory 4 块不动，project_context 旧数据保留（只读，新数据走 Semantic）
step 6: 写入 schema_version=2.2
```

耗时 ≈ 条目数 × 200ms。5000 条以下可接受，超过提供进度条 + 后台跑。

### 9.2 回滚

迁移前拷贝 `data.db → data.db.before_v2.2_backup`。失败时改 `memory.schema_version=2.1` 回退。两个版本共存一个 minor，验证稳定后清理旧代码。

### 9.3 配置项

```yaml
memory:
  schema_version: "2.2"
  scene_analyzer:
    model: "ollama:qwen2.5:3b"
    timeout_ms: 500
    cache_turns: 3
  reflector:
    async: true
    batch_size: 5
    batch_interval_s: 30
  semantic:
    max_entities: 5000
    max_relations: 10000

skills:
  router:
    enabled: true
    top_k: 3
    min_score: 0.3
  manual_override: true
```

## 十、可观测性

### 10.1 日志（延续现风格）

```
[SceneAnalyzer] intent=coding.debug conf=0.9 entities=[project:tars,concept:websocket] shift=false ms=420
[MemoryRouter]  entity=3 episode=2 vector=4 keyword=1 dedup=6 top5=[project:tars,...]
[SkillRouter]   cand=7 picked=[code_assistant(0.82),planner(0.55)] filtered=[translator(0.12)]
[Reflector]     queued=1 batch=5 ops=3 applied=3 ms=1100
```

### 10.2 调试面板（开发模式）

前端 `/debug/memory`：
- 当前 Working Context 原文
- 最近一次 Scene Analyzer 输出
- 最近一次 MemoryRouter top-K 与得分明细
- 实体图可视化（d3 力导向，限 20 节点）

## 十一、测试策略

| 层 | 工具 | 关键 case |
|---|---|---|
| 单元 | pytest | Scene Analyzer JSON 解析、MemoryRouter 打分融合、SkillRouter 冲突解决、Reflector 分流、迁移脚本幂等 |
| 集成 | pytest + 真实小模型 | "提到 Bob 两轮后再问 Bob" 实体路命中；闲聊不进 Episodic；`per_turn` 技能不泄漏 |
| 场景回归 | 固定对话脚本 | 实体线、时间线、话题线各一组 8-12 轮脚本，断言记忆正确更新 |

- 保留 `test_memory_v3.py` 作回归
- 新增 `test_memory_v4.py` / `test_skill_router.py` / `test_scene_analyzer.py`

## 十二、分期上线

| 期 | 时长 | 范围 | 上线策略 |
|---|---|---|---|
| 一期 | 2 周 | 新数据表 + Scene Analyzer + Reflector 分流 + Working Context | 后台写，检索仍走老路 |
| 二期 | 1.5-2 周 | MemoryRouter + SkillRouter + 技能 hooks + 紧急写入通道确认 | 替换主流程，feature flag 可回退 |
| 三期 | 0.5-1 周 | 迁移脚本 + 回填 + 可观测面板 + 文档 | 默认打开 |

**评审点**：一期结束必须评审 Scene Analyzer 准确率。小模型意图识别 <70% 则二期改用主模型或升级小模型。这是整个方案最大不确定性。

## 十三、风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 小模型意图识别不准 | SkillRouter 失效、记忆召回错乱 | 一期评审点；可切主模型；Router `min_score` 兜底 |
| 每轮多一次 LLM 调用延迟 | 对话体感变慢 | 500ms 超时；语义未变复用上轮；`intent: casual` 跳过 |
| 迁移回填 LLM 费时 | 老用户升级卡 | 后台批处理；进度条；允许跳过回填（新数据才进新表） |
| 实体表膨胀 | 检索变慢 | `max_entities` 上限；衰减清理；低 importance + 长期未访问自动删除 |
| Reflector 异步丢失 | 重要信息没写入 | 重试 2 次 + 死信表 + 紧急写入通道绕过队列 |
| 技能 trigger 字段填写门槛 | 社区技能配置复杂 | 提供默认模板 + skillhub 检查 trigger 字段完备性 |

## 十四、开放问题

- `skills/*` 目录下现有 5 个技能的 `trigger` 字段由谁补全？建议官方一起升级并作为兼容模板
- 是否对多用户做准备？本次 scope 内 session 即 user，保留 `user_id` 字段但不强校验
- 实体 ID 命名规范：`type:slug`，slug 由 LLM 产出。需约束 slug 字符集（[a-z0-9_-]）避免乱码
