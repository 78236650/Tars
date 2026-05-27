---
doc_type: spec
status: draft
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# 记忆与技能认知架构重做设计（v2.2）— 调整版

- **日期**：2026-05-09
- **版本**：草案 v1.1（经 DeepSeek TUI 审阅调整）
- **原始版本**：`docs/superpowers/specs/2026-05-09-memory-skill-cognitive-redesign-design.md`
- **调整说明**：6 处架构调整 + 分期策略优化

## 调整摘要

| # | 调整点 | 原设计 | 调整后 | 理由 |
|---|--------|--------|--------|------|
| 1 | Scene Analyzer 调用时机 | 每轮同步 | **异步执行**，结果用于下一轮 | 避免对话延迟翻倍 |
| 2 | Entity ID 生成 | LLM 自由命名 | **确定性哈希** `type:md5(name)[:8]` | 防止同名实体 ID 分裂 |
| 3 | log_episode entity_refs | 必须 ≥1 | **优先但非必须**，无关联标 `standalone` + 降权 | 不丢无实体但有价值的信息 |
| 4 | Core Memory project_context | 禁止写入 | **保留可写**但仅允许替换（set），1-2 行快照 | LLM 需要看到当前项目状态 |
| 5 | 迁移策略 | 启动时批量 LLM 回填 | **懒加载**：检索命中时顺便回填 | 避免启动卡 17 分钟 |
| 6 | HybridSearch 弱化为子路 | 完全替换 | **保留独立实例** + 兜底降级切换 | MemoryRouter 出 bug 时自动回退 |

---

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

- 不做图神经网络、不做知识图谱推理引擎
- 不做多用户跨会话记忆共享（单用户 scope 已足够）
- 不实现技能间通信（hooks 之间通过共享 `SkillContext` 间接协作）

---

## 二、核心思想

> TARS 在每轮对话**结束后异步维护**一份 **场景画像（Working Context）** —— 包括"在聊什么实体、什么意图、有哪些未完成的事"。记忆系统围绕这份画像分层写入与检索，技能系统围绕这份画像动态激活。

> **关键调整**：Scene Analyzer 不是每轮同步调，而是上一轮异步产出、本轮消费。首轮用空 Working Context 兜底，不影响对话延迟。

---

## 三、总体架构

```
┌──────────────────────────────────────────────────────────────┐
│  用户消息                                                      │
└────────────┬─────────────────────────────────────────────────┘
             ▼
    ┌────────────────────┐
    │ 读取 WorkingCtx     │  ← 上一轮 Scene Analyzer 产出的结果
    │ (首轮为空)          │
    └───┬──────────┬─────┘
        │          │
        ▼          ▼
┌──────────────┐ ┌──────────────┐
│ MemoryRouter │ │ SkillRouter  │
│              │ │              │
│ 1. 实体图路  │ │ 基于 trigger │
│ 2. 时间线路  │ │ + working_ctx │
│ 3. 向量路    │ │ 打分选 top-K  │
│ 4. 关键词路  │ │ 临时激活     │
│ 5. 兜底:     │ │              │
│   HybridSrch │ │              │
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
    ┌────────────────────────────────────────────┐
    │ Reflector (后处理)  │ Scene Analyzer (异步)  │
    │ 分层写入:            │ 分析本轮 → 产下一轮 WC  │
    │  - Semantic          │                       │
    │  - Episodic          │                       │
    │  - Core              │                       │
    │  - WorkingCtx 更新   │                       │
    └────────────────────────────────────────────┘
```

---

## 四、记忆四层

### 4.1 Working Context（新增，会话级）

**作用**：记录"当前会话在聊什么"，给 MemoryRouter 和 SkillRouter 做输入。每个 `session_id` 一条。

**表 `working_contexts`**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | TEXT PK | 会话 ID |
| `focus_entities` | JSON | 焦点实体 ID 列表（确定性哈希），最多 8 个，FIFO |
| `current_intent` | TEXT | Scene Analyzer 输出的意图，如 `coding.debug` |
| `intent_confidence` | REAL | 意图置信度 |
| `open_threads` | JSON | 未结话题，最多 5 条 |
| `active_skills` | JSON | 本轮选中的技能 ID 列表 |
| `last_scene_snapshot` | JSON | 最近一次 Scene Analyzer 完整输出 |
| `updated_at` | TEXT | ISO8601 |

**寿命**：跟随 session；超过 72h 未活跃或用户 `/clear` 时清理。

### 4.2 Semantic Memory（新增，实体图）

**Entity ID 规则（调整）**：`类型:md5(规范化名称)[:8]`，例：`person:a1b2c3d4`、`project:e5f6a7b8`

**表 `entities`**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | 确定性哈希 |
| `type` | TEXT | `person` / `project` / `tech` / `concept` / `org` |
| `name` | TEXT | 显示名 |
| `aliases` | JSON | 别名数组，FTS5 索引 |
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

索引：`UNIQUE(from, to, predicate)`

### 4.3 Episodic Memory（升级现 archival）

**表 `archival_memories` 新增字段**：

| 新字段 | 说明 |
|---|---|
| `event_time` | TEXT，事件发生时间 |
| `entity_refs` | JSON，关联实体 ID 列表。**优先但非必须**：无关联时 category=`standalone`，importance 打 7 折 |
| `supersedes` | INTEGER NULL，指向被修正的旧记忆 |

**写入规则收紧**：
- 有 entity_refs → importance 正常
- 无 entity_refs → category=`standalone`，importance×0.7，24h 衰减清理
- 闲聊、一次性操作步骤不进 Episodic

### 4.4 Core Memory（瘦身 + project_context 保留可写）

保持 4 块，`project_context` 保留可写但仅允许替换（set），内容格式：

```
项目: TARS | 阶段: v2.2 开发 | 当前任务: 记忆重构
```

Reflector 的 prompt 按分流规则写入。

---

## 五、Scene Analyzer

### 5.1 调用时机（调整）

**异步执行**：上一轮主 LLM 回复返回后异步跑，结果存入 Working Context，下一轮消费。首轮用空 Working Context 兜底。

```
轮1: 用户msg → 空WC + 主LLM → 回复 + 异步Scene Analyzer → 写入WC
轮2: 用户msg → 读取WC(轮1结果) + 主LLM → 回复 + 异步Scene Analyzer
```

### 5.2 输入

- 本轮用户消息 + 主 LLM 回复
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

注意：entities_mentioned 中的实体不包含 `id`——id 由确定性哈希在写入时计算。

### 5.4 意图标签体系

- `coding.{write|debug|review|refactor|explain}`
- `planning.{decompose|estimate|prioritize}`
- `writing.{draft|edit|translate|summarize}`
- `research.{search|compare|learn}`
- `data.{analyze|transform|visualize}`
- `casual`
- `meta`
- `unknown`

### 5.5 模型与延迟

- 模型：`ollama:qwen2.5:3b`（默认），可配
- 温度 0.1
- 超时 3s，超时跳过，保留旧 Working Context
- 缓存：语义相似度 > 0.95 + 无 topic_shift → 跳过

### 5.6 失败处理

| 失败类型 | 处理 |
|---|---|
| JSON 解析失败 | `intent: unknown`，保守策略 |
| 超时 | 保留上轮 Working Context |
| 模型不可用 | 跳过，仅向量+关键词 |

---

## 六、MemoryRouter

**替代现 `HybridSearch.search()` 单路召回**。

### 6.1 四路 + 兜底

| 路径 | 输入 | 权重 | 命中上限 |
|---|---|---|---|
| 实体路 | Working `focus_entities` + 本轮 `entities_mentioned` | 0.4 | 5 条 episodic + 实体属性 |
| 时间线路 | 焦点实体 + `event_time desc` | 0.2 | 3 条 |
| 向量路 | 用户消息 + `recall_hints` 拼接嵌入 | 0.3 | 5 条 |
| 关键词路（FTS） | 用户消息分词 | 0.1 | 3 条 |
| **兜底路** | MemoryRouter 异常/超时 → 降级为 `HybridSearch` 独立检索 | — | 5 条 |

### 6.2 融合 + 降级

- 同一记忆被多路命中时得分叠加
- 命中记忆刷新 `last_accessed`
- 综合分排序取 top 5-8
- MemoryRouter 异常时自动切换到 `HybridSearch.search()` 纯向量+关键词

### 6.3 注入格式

```
## 相关上下文

### 涉及的实体
- [Bob] 同事，做 Go 后端，在项目 TARS 上

### 最近相关事件
- (2026-05-08) 决定用 Letta 模式重构记忆

### 相关知识
- Function Calling 在 qwen3 上原生支持
```

---

## 七、SkillRouter

**替代现"enable 永久注入"机制**。

### 7.1 技能 YAML 新增字段

```yaml
trigger:
  intents: ["writing.translate", "writing.draft"]
  entities: ["concept:language"]
  keywords: ["翻译", "translate"]
  conditions: "any"
priority: 50
lifecycle: "per_turn"
hooks:
  on_activate: "main.py:on_activate"
  pre_llm: "main.py:pre_llm"
  post_llm: "main.py:post_llm"
```

### 7.2 路由流程

```
1. 取当前 scene 的 intent + entities + 关键词
2. 对每个候选技能打分：intent*0.5 + entity*0.3 + keyword*0.2
3. 过滤 score < 0.3
4. 按 priority desc、score desc 排序，取 top 3
5. 冲突检测：多技能修改同一 persona 块，保留最高 priority
6. 写入 Working Context 的 active_skills
7. 注入 prompt_template；PluginSkill tool 一直在 registry
```

### 7.3 Hooks 安全约束

- Hook 最长 2s，超时跳过
- 只能读写 `ctx.skill_state`（技能私有字典）
- 不允许直接操作数据库或文件系统
- 抛异常 → 仅 prompt 注入，不中断对话

---

## 八、Reflector 重做

### 8.1 操作集

```json
{"op": "upsert_entity", ...}
{"op": "upsert_relation", ...}
{"op": "log_episode", ...}       // entity_refs 可选
{"op": "update_core", ...}        // project_context 仅允许替换
{"op": "forget", ...}
{"op": "noop"}
```

### 8.2 分流规则

| 信息 | 去向 |
|---|---|
| 人/项目/技术/概念首次出现 | `upsert_entity` |
| "A 和 B 有关系"首次或变化 | `upsert_relation` |
| 带时间/决策的事件 | `log_episode` |
| 用户不变偏好/技术栈 | `update_core` |
| project_context 变动 | `update_core`（仅 replace） |
| 过期/错误内容 | `forget` |
| 无新信息 | `noop` |

### 8.3 紧急写入通道

用户明确说"记住 X"时，主 LLM 同步调用 `core_memory_append` 或新增的 `archival_insert`。Reflector 去重跳过本条。

---

## 九、数据迁移（调整）

### 9.1 懒加载策略

- **启动时**：建新表、加字段。旧数据保留不动。
- **运行中**：检索命中旧 archival 时，顺便回填 `entity_refs` 存入新表。
- **不执行**：批量全量 LLM 回填。

### 9.2 回滚

迁移前拷贝 `data.db → data.db.before_v2.2_backup`。

---

## 十、分期上线（调整）

| 期 | 时长 | 范围 | 策略 |
|---|---|---|---|
| **1a** | 3 天 | 新表 + Scene Analyzer（异步版）+ Working Context 读写 | 后台写，不接主流程 |
| **1b** | 2 天 | Reflector 分流写入（entity/relation/episode） | 写新结构，检索仍走老路 |
| **评审** | — | 看数据质量 + Scene Analyzer 准确率 | 低于 70% 则切主模型 |
| **二期** | 5-7 天 | MemoryRouter + SkillRouter + Hooks + 紧急写入通道 | 替换主流程，feature flag 可退 |
| **三期** | 2-3 天 | 懒加载迁移 + 调试面板 + 文档 | 默认打开 |

---

*文档版本: v1.1（调整版）*  
*审阅者: DeepSeek TUI V4*  
*日期: 2026-05-09*
