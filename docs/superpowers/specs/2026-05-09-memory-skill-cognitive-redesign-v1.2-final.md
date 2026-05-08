# 记忆与技能认知架构重做设计（v2.2）— v1.2 整合版

- **日期**：2026-05-09
- **版本**：草案 v1.2（整合 DeepSeek 审阅 + Kiro 反驳）
- **原始版本**：`2026-05-09-memory-skill-cognitive-redesign-design.md`（v1.0）
- **审阅版本**：`2026-05-09-memory-skill-cognitive-redesign-v1.1-reviewed.md`（v1.1）
- **本版性质**：在 v1.0 基础上选择性吸收 v1.1 的 6 条调整，另补 3 处增强

## 相对 v1.1 的调整决策

| # | v1.1 提议 | v1.2 决定 | 核心理由 |
|---|---|---|---|
| 1 | Scene Analyzer 改异步，下一轮消费 | **改良同步**：同步为主 + 快速路径跳过 + 异步作为降级 | 异步会让首轮和话题切换慢一拍，直接打脸"不自动激活"修复目标；延迟用缓存消解 |
| 2 | Entity ID 改确定性哈希 | **采纳，并补 aliases 合并流程** | 纯哈希只把分裂延后——Bob/Bob Smith/老王 仍然会生成三个不同 hash |
| 3 | `log_episode` 放宽 entity_refs | **拒绝，改为扩展实体类型** | 硬约束是防止 Reflector 偷懒把闲聊存成 standalone 的关键；改为允许隐式创建 `concept:*` / `decision:*` 兜底 |
| 4 | `project_context` 保留可写（replace） | **采纳，并限定由 Reflector 从 Semantic 派生** | 避免 LLM 直接写导致与 Semantic 的 project entity 双写冲突 |
| 5 | 迁移改懒加载 | **采纳，并加后台 worker + 手动触发** | 纯懒加载会把"启动卡 17 分钟"摊成"首次查询卡"；冷门记忆变僵尸 |
| 6 | HybridSearch 独立兜底 | **采纳，并明确"仅异常降级"** | 正常情况下 MemoryRouter 向量路+关键词路已覆盖其能力，不参与融合打分 |
| 7 | 分期压缩到 12-15 天 | **拒绝，保留原 4.5 周** | Scene Analyzer prompt 调优 + Reflector 分流 + 真实对话评估，压不动 |

## 相对 v1.0 的新增

- **快速路径跳过**：短消息 + 无 topic_shift → 复用上轮 WC，消解同步调用延迟
- **Aliases 合并流程**：写入实体时走 "探测 → 合并" 避免同实体分裂
- **兜底实体类型**：`concept:*` / `decision:*` 让"无人物无项目但有价值"的信息仍能关联实体落地
- **后台迁移 worker**：低优先级持续回填旧数据

---

## 一、背景与目标

### 1.1 现状痛点

v2.1 已实现 Letta 风格的 Core + Archival + Reflector，但用户反馈系统仍"不够聪明、技能触发呆板"。

记忆四症：
1. **该想起没想起**
2. **存了一堆没用的**
3. **记忆错乱/不进化**
4. **不能连成线**（实体/时间/话题三种连贯全缺）

技能三症：
5. **不自动激活**
6. **没组合/没优先级**
7. **技能表达力弱**

### 1.2 根本原因

记忆是"条目堆"、技能是"开关"，两者都缺少 **Agent 对当前场景的自我感知**。

### 1.3 目标

- 建立"场景画像 → 记忆分层 → 技能动态路由"统一认知架构
- 覆盖实体、时间线、会话三种连贯
- 技能依据场景自动激活、组合、仲裁
- 平滑迁移，老数据不丢

### 1.4 非目标

- 不做图神经网络、不做知识图谱推理引擎
- 不做多用户跨会话记忆共享
- 不实现技能间通信（hooks 只通过共享 `SkillContext` 间接协作）

## 二、核心思想

> TARS 在每轮对话前**同步**维护一份 **场景画像（Working Context）** —— 包括"在聊什么实体、什么意图、有哪些未完成的事"。记忆系统围绕这份画像分层写入与检索，技能系统围绕这份画像动态激活。

**关键取舍**：Scene Analyzer 默认同步，靠"快速路径跳过 + 小模型低延迟 + 超时降级"保障体感。异步作为最后降级手段，不作为默认。

## 三、总体架构

```
┌──────────────────────────────────────────────────────────────┐
│  用户消息                                                      │
└────────────┬─────────────────────────────────────────────────┘
             ▼
    ┌────────────────────┐
    │ 快速路径判断         │  消息短 + 无 topic 信号 + WC 新鲜
    │ 命中则复用上轮 WC    │  →  跳过 Scene Analyzer
    └───┬──────────┬─────┘
        │(未命中)  │(命中/跳过)
        ▼          │
    ┌────────────────┐
    │ Scene Analyzer │  同步调小模型，500ms 预算
    │ 超时降级 → 复用 │
    │ 上轮 WC         │
    └───┬──────────┬─┘
        │          │
        ▼          ▼
┌──────────────┐ ┌──────────────┐
│ MemoryRouter │ │ SkillRouter  │
│              │ │              │
│ 实体/时间/   │ │ trigger +    │
│ 向量/关键词  │ │ scene 打分   │
│              │ │              │
│ 异常→兜底:   │ │ top-K 激活   │
│ HybridSearch │ │              │
└──────┬───────┘ └──────┬───────┘
       ▼                ▼
  ┌─────────────────────────────┐
  │ System Prompt 拼装           │
  └──────────────┬──────────────┘
                 ▼
            主 LLM 对话
                 ▼
    ┌────────────────────────────┐
    │ Reflector (异步批处理)       │
    │  - upsert_entity/relation   │
    │  - log_episode              │
    │  - update_core              │
    │  - forget                   │
    │  - 紧急写入通道去重           │
    └────────────────────────────┘
```

### 3.1 新增组件

| 组件 | 类型 | 说明 |
|---|---|---|
| Scene Analyzer | 服务 | 同步调小模型，带快速路径 |
| Working Context | 数据表 | 会话级短期"在聊什么" |
| Semantic Memory | 数据表（entities + relations） | 实体图，哈希 ID + aliases 合并 |
| Episodic Memory | 现 archival 升级 | 加时间戳语义 |
| MemoryRouter | 服务 | 四路召回 + 融合打分 + HybridSearch 兜底降级 |
| SkillRouter | 服务 | 每轮动态选技能 + hooks |

## 四、记忆四层

### 4.1 Working Context（会话级）

`working_contexts` 表：

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | TEXT PK | 会话 ID |
| `focus_entities` | JSON | 焦点实体 ID 列表（哈希），≤8，FIFO |
| `current_intent` | TEXT | `coding.debug` / `writing.translate` 等 |
| `intent_confidence` | REAL | 意图置信度 |
| `open_threads` | JSON | 未结话题，≤5 |
| `active_skills` | JSON | 本轮选中技能 ID |
| `last_scene_snapshot` | JSON | 上次 Scene Analyzer 完整输出 |
| `last_user_msg_hash` | TEXT | 用户消息规范化哈希（快速路径用） |
| `last_user_msg_embedding` | BLOB | 嵌入缓存（快速路径用） |
| `updated_at` | TEXT | ISO8601 |

**寿命**：72h 未活跃或 `/clear` 清理。

### 4.2 Semantic Memory（实体图）

**Entity ID 规则（v1.2）**：
- 格式：`<type>:md5(normalize(name))[:8]`
- `normalize()`：小写 + 去首尾空格 + 连续空白合并为单空格 + 移除标点
- 例：`Bob Smith` → `person:a1b2c3d4`；`TARS`/`tars`/`Tars` → 同一 `project:e5f6a7b8`

**Aliases 合并流程**（v1.2 关键补充）：

```
Reflector 要 upsert 实体 name="老王" type=person 时：
1. 算 primary_id = person:md5(normalize("老王"))[:8]
2. 若 primary_id 已存在 → 直接合并 attributes，返回
3. 否则：FTS5 查 entities.aliases 看是否命中已有实体
     → 命中（如 person:a1b2c3d4 的 aliases 含 "老王" 或语义相似）
         → 把 "老王" 加到该实体 aliases，不新建，返回已有 id
     → 未命中
         → 语义检索 entities.name：用 name 嵌入比对同 type 实体
         → 相似度 > 0.85 → 合并到相似实体
         → 否则 → 新建 person:primary_id
4. 合并时记录 alias_merge 日志便于审计
```

**写入时哈希由后端计算，不由 LLM 产出**，避免 LLM 算错。

`entities` 表：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | `<type>:<md5_8>` |
| `type` | TEXT | `person`/`project`/`tech`/`concept`/`org`/`decision` |
| `name` | TEXT | 显示名 |
| `aliases` | JSON | 别名数组 |
| `attributes` | JSON | 灵活属性袋 |
| `attributes_history` | JSON | 属性变更历史 |
| `importance` | REAL | 衰减 |
| `last_accessed` | TEXT | |
| `created_at` | TEXT | |

索引：`idx_entities_type` / `idx_entities_name`；FTS5 表 `entities_aliases_fts(id, aliases)` 用于别名命中

`relations` 表：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INTEGER PK | |
| `from_entity` | TEXT | |
| `to_entity` | TEXT | |
| `predicate` | TEXT | `works_on`/`uses`/`colleague_of`/`part_of` 等 |
| `confidence` | REAL | 0-1 |
| `source_memory_id` | INTEGER NULL | |
| `created_at` | TEXT | |

索引：`UNIQUE(from_entity, to_entity, predicate)` / `idx_relations_from` / `idx_relations_to`

### 4.3 Episodic Memory（升级现 archival）

**`archival_memories` 新增字段**：

| 新字段 | 说明 |
|---|---|
| `event_time` | TEXT，事件发生时间 |
| `entity_refs` | JSON，关联实体 ID 列表，**必须 ≥1** |
| `supersedes` | INTEGER NULL，指向被修正的旧记忆 |

**硬约束（v1.2 维持 v1.0 立场）**：

- `log_episode` 必须带 `entity_refs`（≥1），否则 Reflector 丢弃本条
- 无人物/无项目关联的"有价值"信息 → 通过**兜底实体类型**承载：
  - `concept:*` 纯知识类（"Function Calling 在 qwen3 原生支持"→ 关联 `concept:function_calling`, `tech:qwen3`）
  - `decision:*` 决策类（"我们决定用 Letta 模式"→ 关联 `decision:memory_architecture`）
- Reflector prompt 明确提示"若找不到实体，请创建 concept 或 decision 兜底实体"
- 同内容 24h 内 upsert ≥3 次且 `importance<0.5` → 标"琐碎"，7 天不出现在检索

**不采纳 v1.1 的 standalone 字段**：见本文档顶部调整表理由。

### 4.4 Core Memory（4 块保留）

4 块保留，`project_context` 恢复可写但**仅允许 replace**（不 append）：

- 内容格式固定：`项目: <name> | 阶段: <phase> | 当前任务: <task>`（1-2 行）
- 数据来源：**由 Reflector 从 Semantic 层的 project entity 和最新 decision 实体派生**，不允许 LLM 直接写任意内容
- 派生触发：project entity 的 attributes 变化或新 decision 实体出现时，Reflector 重算并 replace
- LLM 直接调 `core_memory_replace(block="project_context", ...)` 时后端校验格式，不符合则拒绝

`user_profile` / `working_principles` / `persona` 三块保留 append 语义，由 Reflector 正常写入。

## 五、Scene Analyzer

### 5.1 调用时机（v1.2 维持同步）

**默认同步**：每轮用户消息到达后、主 LLM 生成前调用。带两级优化：

**快速路径**（一级优化，无 LLM 调用）：

```
条件全部满足则跳过 Scene Analyzer，复用上轮 Working Context：
  1. 消息长度 < 50 字符
  2. 与上轮 last_user_msg_embedding 余弦相似度 > 0.9
  3. 不含疑问句/话题切换关键词（"另外"/"换个话题"/"对了"/"?" 等）
  4. Working Context 更新时间 < 5 分钟
```

命中率预估：40-60% 的对话（追问、短消息、同话题深挖）。

**语义缓存**（二级优化）：

快速路径未命中时，算当前消息嵌入，与上轮消息嵌入比较：
- 相似度 > 0.95 且无 topic_shift 信号 → 沿用上轮 scene 结果，只更新 `last_user_msg_*`
- 否则真正调用 Scene Analyzer

**超时降级**（三级兜底）：

- 500ms 预算
- 超时 3s → 跳过，保留上轮 Working Context
- 模型不可用 → `intent: unknown`，Router 走保守策略

**异步降级**（极端情况）：

仅当用户主动配置 `scene_analyzer.mode: async` 时启用 v1.1 提的下一轮消费模式。**不作为默认**。

### 5.2 输入

- 当前用户消息（截断 2k）
- 最近 3 轮对话摘要（由 Reflector 产出，缓存在 Working Context）
- 当前 Working Context

### 5.3 输出（严格 JSON）

```json
{
  "intent": "coding.debug",
  "intent_confidence": 0.9,
  "entities_mentioned": [
    {"name": "TARS", "type": "project", "is_new": false},
    {"name": "WebSocket", "type": "concept", "is_new": false}
  ],
  "topic_shift": false,
  "open_thread_refs": ["v2.2 记忆重做"],
  "needs_memory_recall": true,
  "recall_hints": ["WebSocket 持久连接", "wsStore"]
}
```

**entities_mentioned 不含 id**——由后端按 §4.2 的 normalize + 哈希 + aliases 合并流程计算。

### 5.4 意图标签体系

- `coding.{write|debug|review|refactor|explain}`
- `planning.{decompose|estimate|prioritize}`
- `writing.{draft|edit|translate|summarize}`
- `research.{search|compare|learn}`
- `data.{analyze|transform|visualize}`
- `casual` / `meta` / `unknown`

技能包可在 `skill.yaml` 的 `trigger.intents` 声明响应哪些意图，允许新增自定义意图名。

### 5.5 模型配置

```yaml
scene_analyzer:
  mode: sync                         # sync | async（极端情况）
  model: ollama:qwen2.5:3b           # 可配
  temperature: 0.1
  timeout_ms: 500
  hard_timeout_ms: 3000
  fast_path:
    enabled: true
    max_msg_length: 50
    embedding_sim_threshold: 0.9
    wc_freshness_minutes: 5
  semantic_cache:
    enabled: true
    embedding_sim_threshold: 0.95
```

## 六、MemoryRouter

### 6.1 四路 + 异常兜底

| 路径 | 输入 | 权重 | 命中上限 |
|---|---|---|---|
| 实体路 | `focus_entities` + `entities_mentioned` | 0.4 | 5 条 episodic + 实体属性 + 一跳关系 |
| 时间线路 | 焦点实体 + `event_time desc` | 0.2 | 3 条 |
| 向量路 | 用户消息 + `recall_hints` 拼接嵌入 | 0.3 | 5 条 |
| 关键词路（FTS） | 用户消息分词 | 0.1 | 3 条 |

**HybridSearch 作为兜底降级**（v1.2 明确）：

- 正常情况下**不参与**融合打分
- 触发条件：
  - MemoryRouter 四路中有 ≥2 路异常/超时
  - 或 MemoryRouter 总耗时 > 1s
  - 或 feature flag `memory_router.disabled=true` 手动回退
- 触发时直接调 `HybridSearch.search(user_msg, top_k=5)` 作为最终结果，跳过融合

**不是"第五路并发跑"**——那样会浪费计算且语义不对。

### 6.2 融合打分

- 同一记忆被多路命中 → 得分叠加
- 命中记忆刷新 `last_accessed`（沿用 reinforce）
- 综合分排序取 top 5-8

### 6.3 降级（场景自适应）

- `needs_memory_recall=false` → 仅向量路跑最小检索（top 2）或跳过
- `intent: casual` → 跳过 Episodic，只查 Core + Working

### 6.4 注入格式

```
## 相关上下文

### 涉及的实体
- [Bob] 同事，Go 后端，在项目 TARS 上
- [项目 TARS] v2.1.0，FastAPI + Vue3

### 最近相关事件
- (2026-05-08) 决定用 Letta 模式重构记忆
- (2026-05-09) Bob 提议 SkillHub 用 GitHub Releases

### 相关知识
- Function Calling 在 qwen3 原生支持
```

## 七、SkillRouter

### 7.1 技能 YAML 新增字段

```yaml
trigger:
  intents: ["writing.translate", "writing.draft"]
  entities: ["concept:language"]
  keywords: ["翻译", "translate", "英译中"]
  conditions: "any"               # any | all
priority: 50                        # 0-100
lifecycle: "per_turn"               # per_turn | sticky | session
hooks:
  on_activate: "main.py:on_activate"
  pre_llm: "main.py:pre_llm"
  post_llm: "main.py:post_llm"
```

### 7.2 生命周期

| 值 | 含义 |
|---|---|
| `per_turn` | 默认；本轮激活，下轮 Router 重新决定 |
| `sticky` | 激活后保持到会话结束或 `/skill off` |
| `session` | 会话开启即激活 |

### 7.3 路由流程

```
1. 取当前 scene 的 intent + entities + 消息关键词
2. 对每个已 enable 的候选打分：
     score = intent*0.5 + entity*0.3 + keyword*0.2
3. 过滤 score < 0.3
4. priority desc、score desc 排序，取 top 3
5. 冲突：多技能改同一 persona 块 → 留最高 priority
6. 写入 Working Context.active_skills
7. 注入 prompt_template；PluginSkill tool 常驻 registry
```

### 7.4 手动控制

- `/skill <id>` → 强制激活为 sticky
- `/skill off <id>` → 本轮及后续不能选
- `/auto` → 回到自动路由

### 7.5 分数匹配算法

- `intent_match`：精确 1.0；前缀（`writing.*`）0.7；无 0
- `entity_match`：每命中一实体 0.5，上限 1.0
- `keyword_match`：任一命中 1.0；否则 0

### 7.6 Hooks（本期落地）

**签名**：
```python
def pre_llm(ctx: SkillContext) -> SkillContext: ...
```

**`SkillContext` 暴露**：
- `working_context`：只读快照
- `messages`：可读可改
- `system_prompt_parts`：可追加
- `tool_registry`：可临时注册/禁用（仅本轮）
- `skill_state`：技能私有字典（持久化到 Working Context）
- `set_response_patch(fn)`：注册对主 LLM 回复的后处理

**安全约束**：
- 2s 超时跳过并记日志
- 只能读写自己的 `skill_state`
- 不允许直接操作 DB 或 FS，必须通过 tool registry
- 抛异常 → 降级为仅 prompt 注入，不中断对话

**落地**：三个 hook 全部实现，提供示例 `skills/example_hook/`。

## 八、Reflector 重做

### 8.1 操作集

```json
[
  {"op": "upsert_entity", "type": "person", "name": "Bob",
   "aliases": ["老王"], "attributes": {"role": "同事"}, "confidence": 0.9},

  {"op": "upsert_relation", "from_name": "Bob", "from_type": "person",
   "to_name": "TARS", "to_type": "project",
   "predicate": "works_on", "confidence": 0.9},

  {"op": "log_episode", "content": "Bob 提议 SkillHub 用 GitHub Releases",
   "event_time": "2026-05-08T14:30:00+08:00",
   "entity_refs_by_name": [
     {"name": "Bob", "type": "person"},
     {"name": "TARS", "type": "project"}
   ],
   "importance": 0.75, "supersedes": null},

  {"op": "update_core", "block": "user_profile",
   "action": "append", "new": "用户偏好 monorepo"},

  {"op": "forget", "target": "entity|episode|core", "id_or_keyword": "..."},

  {"op": "noop"}
]
```

**LLM 只给 name+type，后端算哈希 ID**（避免 LLM 算错）。

### 8.2 分流规则

| 信息 | 去向 |
|---|---|
| 人/项目/技术/概念首次出现 | `upsert_entity` |
| 纯知识无人物无项目 | `upsert_entity` → `concept:*` |
| 重大决策 | `upsert_entity` → `decision:*` |
| "A 和 B 有关系"首次或变 | `upsert_relation` |
| 带时间/决策/关联实体的事件 | `log_episode` |
| 用户不变偏好/技术栈 | `update_core`（user_profile/working_principles/persona） |
| project 状态变化 | Reflector 自动派生 `project_context` replace |
| 过期/错误 | `forget` |
| 无新信息 | `noop` |

**硬约束**：
- `log_episode` 必须带 ≥1 entity_ref，否则丢弃
- 同内容 24h 内 upsert ≥3 次且 `importance<0.5` → 琐碎，7 天不出检索
- Reflector prompt 明确提示"若找不到实体，请创建 concept/decision 兜底实体"

### 8.3 冲突解决

`upsert_entity` / `upsert_relation` 带 `confidence`：
- 高置信度覆盖低置信度
- 属性合并：新属性追加，同名属性新值生效，旧值进 `attributes_history`
- 矛盾属性保留历史不直接丢

### 8.4 异步 + 批处理

- 异步队列，不阻塞对话返回
- 每 30s 或积压 5 条触发批量
- 失败重试 2 次，最终失败入死信表
- 保留紧急写入通道（§8.5）

### 8.5 紧急写入通道

**触发语义**：用户明确说"记住 X"时，主 LLM **立即同步**调用：

- `core_memory_append(block, content)` —— 同步写 Core
- `archival_insert(content, category, importance=0.9, entity_hints=[{"name":"","type":""}])` —— 同步写 Episodic

**工具 description 要点**：
- "用户**明确**要求记住 / 强调"这条必须记住"时调用。Reflector 已覆盖一般信息，不要为普通陈述反复调用"
- 调用后应在回复里告知"已记住 X"形成闭环

**Reflector 去重**：异步处理时检查本轮 tool_calls 日志，跳过紧急通道已写入的内容。

## 九、数据迁移与兼容

### 9.1 三步走策略（v1.2）

| 阶段 | 动作 | 时机 |
|---|---|---|
| 启动 | 建新表、加字段、拷贝 `data.db → data.db.before_v2.2_backup`、写 `schema_version=2.2` | 首次启动 v2.2 |
| 运行时热回填 | 检索命中旧 archival（`entity_refs IS NULL`）时，同步调 Reflector 小模型回填 entity_refs + event_time | 每次 MemoryRouter 命中 |
| 后台 worker | 独立线程每 30s 取 10 条 `entity_refs IS NULL` 的旧记录跑回填，低优先级 | 系统启动即运行 |

**不批量启动回填**——避免 17 分钟启动卡顿。

**手动触发**：设置页加"立即完成迁移"按钮，前端 WS 推进度条。用户急性子时可一键跑完。

### 9.2 回滚

改 `memory.schema_version=2.1` → 旧代码路径生效。两个版本共存一个 minor，验证稳定后再清理旧代码。

### 9.3 配置项

```yaml
memory:
  schema_version: "2.2"
  scene_analyzer:
    mode: sync
    model: ollama:qwen2.5:3b
    timeout_ms: 500
    hard_timeout_ms: 3000
    fast_path:
      enabled: true
      max_msg_length: 50
      embedding_sim_threshold: 0.9
      wc_freshness_minutes: 5
    semantic_cache:
      enabled: true
      embedding_sim_threshold: 0.95
  reflector:
    async: true
    batch_size: 5
    batch_interval_s: 30
  semantic:
    max_entities: 5000
    max_relations: 10000
    alias_merge_sim_threshold: 0.85
  migration:
    lazy: true
    background_worker:
      enabled: true
      interval_s: 30
      batch_size: 10

skills:
  router:
    enabled: true
    top_k: 3
    min_score: 0.3
  manual_override: true
  hooks:
    enabled: true
    timeout_ms: 2000
```

## 十、可观测性

### 10.1 日志

```
[SceneAnalyzer] fast_path=hit ms=2
[SceneAnalyzer] intent=coding.debug conf=0.9 entities=[project:e5f6,concept:a1b2] shift=false ms=420
[MemoryRouter]  entity=3 episode=2 vector=4 keyword=1 dedup=6 top5=[project:e5f6,...]
[MemoryRouter]  FALLBACK→HybridSearch reason=entity_path_timeout
[SkillRouter]   cand=7 picked=[code_assistant(0.82),planner(0.55)] filtered=[translator(0.12)]
[AliasMerge]    new=老王 merged_into=person:a1b2c3d4 reason=fts_hit
[Reflector]     queued=1 batch=5 ops=3 applied=3 ms=1100
[Migration]     backfilled id=234 entities=[person:a1b2,project:e5f6]
```

### 10.2 调试面板（开发模式 `/debug/memory`）

- Working Context 原文
- 最近 Scene Analyzer 输出 + fast_path 命中状态
- 最近 MemoryRouter top-K 与得分明细、降级状态
- 实体图可视化（d3 力导向，限 20 节点）
- 迁移进度（剩余未回填条数 + ETA）
- Hook 执行日志（技能 / hook / 耗时 / 是否超时）

## 十一、测试策略

| 层 | 工具 | 关键 case |
|---|---|---|
| 单元 | pytest | Scene Analyzer JSON 解析、fast_path 判定、哈希 ID + 归一化、aliases 合并、MemoryRouter 打分融合、HybridSearch 兜底切换、SkillRouter 冲突、Hook 超时降级、Reflector 分流、紧急写入去重、迁移幂等 |
| 集成 | pytest + 真实小模型 | "提到 Bob 两轮后问 Bob" 实体路命中；别名变体不分裂；闲聊不进 Episodic；`per_turn` 技能不泄漏；fast_path 命中率；兜底实体正确创建 |
| 场景回归 | 固定对话脚本 | 实体线 / 时间线 / 话题线各 8-12 轮，断言记忆正确更新；别名合并 5 轮脚本 |

- 保留 `test_memory_v3.py` 作回归
- 新增 `test_memory_v4.py` / `test_skill_router.py` / `test_scene_analyzer.py` / `test_entity_merge.py` / `test_migration.py`

## 十二、分期上线（v1.2 保留 4.5 周）

| 期 | 时长 | 范围 | 策略 |
|---|---|---|---|
| **1a** | 1 周 | 新表 + Entity ID/aliases 合并 + Working Context 读写 + 后台迁移 worker | 仅建表和写入，不接主流程 |
| **1b** | 1 周 | Scene Analyzer（同步 + fast_path + 语义缓存）+ Reflector 分流写入（entity/relation/episode + 兜底 concept/decision） | 写新结构，检索仍走老路 |
| **评审点** | — | 评估 Scene Analyzer 准确率 + aliases 合并正确率 + fast_path 命中率 | 准确率 <70% 则切主模型或升级小模型 |
| **二期** | 1.5-2 周 | MemoryRouter（含 HybridSearch 兜底）+ SkillRouter + Hooks + 紧急写入通道 + 调试面板 | 替换主流程，feature flag 可回退 |
| **三期** | 0.5-1 周 | 热回填 + 手动迁移按钮 + 文档 + 默认开关打开 | 完整上线 |

总计 ≈ 4.5 周。

**评审点硬要求**：
- Scene Analyzer intent 准确率 ≥ 70%（人工标注 100 轮对话）
- Fast path 命中率 ≥ 35%
- Aliases 合并正确率 ≥ 90%（同一实体不分裂）
- 任一不达标 → 评估切主模型或调整方案，不强行上二期

## 十三、风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 小模型意图识别不准 | SkillRouter 失效、召回错乱 | 1b 评审点；可切主模型；`min_score` 兜底；HybridSearch 降级 |
| Scene Analyzer 同步延迟 | 对话变慢 | fast_path 消 40-60% 调用；语义缓存消 10-20%；500ms 超时 |
| 迁移回填长尾 | 冷门记忆永远旧格式 | 后台 worker 持续跑；手动按钮兜底；检索命中热回填 |
| 实体表膨胀 | 检索变慢 | `max_entities` 上限；衰减清理；低 importance + 长期未访问自动删除 |
| Aliases 合并误杀 | 两个人都叫 Bob 合成一个 | `attributes` 冲突阈值告警；合并审计日志；用户可手动拆分（后续） |
| Reflector 异步丢失 | 重要信息没写入 | 重试 2 次 + 死信表 + 紧急写入通道绕过队列 |
| Hook 恶意/卡死 | 对话中断 | 2s 超时；沙箱化 skill_state；不允许直接操作 DB/FS |
| 技能 trigger 填写门槛 | 社区技能配置复杂 | 默认模板 + skillhub 校验 trigger 完备性 |
| project_context 派生脏数据 | 显示错乱 | 固定格式校验；Reflector 派生失败保留旧值不覆盖 |

## 十四、开放问题

- 现有 5 个内置技能的 `trigger` 字段由谁补全：建议官方统一升级作兼容模板
- 用户手动拆分被误合并实体的 UI：三期之后独立专项
- Entity ID 迁移：旧数据回填时若同名实体在新旧表都存在如何处理（方案：以新表 id 为准，旧 archival 的 entity_refs 重新计算）
- 评审点不达标时是降级方案还是延期：需事先约定止损条件

## 十五、版本对比速查

| 议题 | v1.0 | v1.1-reviewed | v1.2（本版） |
|---|---|---|---|
| Scene Analyzer 调用 | 同步每轮 | 异步下轮消费 | 同步 + fast_path + 语义缓存 + 异步降级 |
| Entity ID | LLM 命名 | 纯哈希 | 哈希 + aliases 合并流程 |
| log_episode entity_refs | 必须 ≥1 | 可选 + 降权 | 必须 ≥1 + 兜底 concept/decision |
| project_context | 禁写 | 可 replace | Reflector 从 Semantic 派生 + 格式校验 |
| 迁移 | 启动批量 | 纯懒加载 | 热回填 + 后台 worker + 手动触发 |
| HybridSearch | 替换 | 作为第五路 | 作为异常兜底降级 |
| 分期 | 4.5 周 | 12-15 天 | 4.5 周 + 评审点硬门槛 |

---

*文档版本: v1.2 整合版*
*作者: Kiro*
*基于: DeepSeek TUI V4 审阅 + Kiro 反驳与增补*
*日期: 2026-05-09*
