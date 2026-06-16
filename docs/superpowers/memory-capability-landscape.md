# TARS 记忆系统能力全景图

> v5.0.5/A3+ · 更新日期：2026-06-16 · 测试：48/48 通过

---

## 一、总体架构

```
                           ┌──────────────────────────────────┐
                           │         用户对话                   │
                           └──────────────┬───────────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     ▼                     │
                    │          Scene Analyzer                   │
                    │      (意图识别 / 实体检测)                  │
                    │                     │                     │
                    │   ┌─────────────────┼─────────────────┐   │
                    │   ▼                 ▼                 ▼   │
                    │ Working         System Prompt       Agent │
                    │ Context         构建与注入          执行   │
                    │                     │                     │
                    │   ┌─────────────────┘                     │
                    │   ▼                                       │
                    │ MemoryManager.get_context_for_query()      │
                    │   ├─ Core Memory (始终注入)               │
                    │   ├─ HybridSearch (语义+FTS+衰减)         │
                    │   ├─ _cross_entity_discovery (关联发现)   │
                    │   └─ _proactive_reminders (主动提醒)      │
                    └───────────────────────────────────────────┘
                                          │
                    每轮对话后异步触发     │
                    ┌─────────────────────┼─────────────────────┐
                    │                     ▼                     │
                    │              Reflector                     │
                    │         (10 种 op，三层降级)               │
                    │   ┌───────────────────────────────────┐   │
                    │   │ upsert_entity    upsert_relation   │   │
                    │   │ log_episode      update_episode    │   │
                    │   │ log_solution     log_procedure     │   │
                    │   │ log_correction   update_core       │   │
                    │   │ forget           noop              │   │
                    │   └───────────────────────────────────┘   │
                    │                     │                     │
                    │     ┌───────────────┼───────────────┐     │
                    │     ▼               ▼               ▼     │
                    │  entities       memories          core    │
                    │  relations      (SQLite/PG)       memory  │
                    │     │               │               │     │
                    │     └───────┬───────┘               │     │
                    │             ▼                       │     │
                    │      Entity Tree                    │     │
                    │      (实体记忆树)                    │     │
                    └─────────────────────────────────────┘     │
                                          │                     │
                    后台维护               │                     │
                    ┌─────────────────────┼─────────────────────┐
                    │  SleepAgent        Compressor              │
                    │  (去重/冲突/衰减)   (手动合并)              │
                    │                                           │
                    │  MemoryScheduler   KB Promotion            │
                    │  (定时调度)        (记忆→知识库)            │
                    └───────────────────────────────────────────┘
                                          │
                    每 50 轮触发          │
                    ┌─────────────────────┼─────────────────────┐
                    │           Evolution System                 │
                    │  ┌─────────────────────────────────────┐   │
                    │  │  MemoryAwareAnalyzer                 │   │
                    │  │  └─ 分析 correction/solution 模式    │   │
                    │  │  └─ 生成 avoidance_rules             │   │
                    │  │  └─ 生成 recommendations             │   │
                    │  ├─────────────────────────────────────┤   │
                    │  │  MemoryFeedbackBridge                │   │
                    │  │  └─ 规则 → working_principles        │   │
                    │  │  └─ 方案 → pinned memory             │   │
                    │  │  └─ 反复纠正 → lesson_learned        │   │
                    │  └─────────────────────────────────────┘   │
                    └───────────────────────────────────────────┘
```

---

## 二、组件清单与职责

### 2.1 写入层

| 组件 | 文件 | 职责 |
|------|------|------|
| **Reflector** | `memory/reflector.py` | 每轮对话后异步反思，10 种 op 分流写入；三层降级（LLM→启发式→最小归档） |
| **ArchivalManager** | `memory/archival.py` | 长期记忆写入，含 MemoryDeduplicator 四层去重（精确/包含/Jaccard/语义） |
| **LLMMemoryExtractor** | `memory/extractor.py` | 技术要点提取（供前端预览确认）；HeuristicTurnExtractor/RegexExtractor 兜底 |

#### Reflector 10 种 op

| op | 写入目标 | importance | 说明 |
|----|---------|------------|------|
| `upsert_entity` | entities 表 | 0.5-0.8 | 人/项目/技术/港航实体注册 |
| `upsert_relation` | relations 表 | 0.5-0.7 | 实体间关系 |
| `log_episode` | memories (episodic) | 0.5-0.7 | 事件/对话记录；写入前去重检查 |
| `update_episode` | memories (更新) | 0.5-0.7 | 对已有 episodic 的增量更新 |
| `log_solution` | memories (solution) | 0.8 | 问题→根因→方案→关键认知 |
| `log_procedure` | memories (procedure) | 0.9 | 可复用 SOP + 触发词 |
| `log_correction` | memories (correction) | 0.85 | 用户纠正记录 |
| `update_core` | core_memory_blocks | - | persona/user_profile/project_context/working_principles |
| `forget` | core_memory_blocks | - | 删除过期/错误行 |
| `noop` | - | - | 无操作 |

### 2.2 存储层

| 存储单元 | 表/结构 | 说明 |
|----------|---------|------|
| **Core Memory** | `core_memory_blocks` | 4 块固定区块：persona / user_profile / project_context / working_principles；每用户私有；带自动 trim（2048B）+ 行去重 + 行数限制（30行） |
| **Memories** | `memories` + FTS5 | 主记忆表，字段：id / content / category / importance / memory_type / entity_refs / pinned / compressed_from / user_id / scope |
| **Entities** | `entities` + FTS5 aliases | 实体注册表，type+name→MD5哈希ID；别名搜索 |
| **Relations** | `relations` | 实体间有向关系（from→predicate→to） |
| **Vector Store** | Chroma（优先）/ SQLite BLOB | 语义检索向量；生产 Chroma，开发/降级 SQLite |
| **KB / Wiki** | `documents` + `wiki/` | 知识库文档（由 KB Promotion 或手动创建） |
| **Working Context** | `working_contexts` | 会话级场景画像（focus_entities / intent / open_threads） |

#### memory_type 分类

| memory_type | 含义 | 衰减策略 |
|-------------|------|----------|
| `episodic` | 对话事件 | 标准 Ebbinghaus 衰减 |
| `longterm` | 晋升的长期记忆 | 慢衰减（importance 高时半衰期 720h） |
| `procedural` | solution/procedure/correction | 慢衰减 + 检索加权 ×1.15 |
| `compressed` | 手动压缩合并产物 | 检索降权 ×0.9 |

#### category 分类

| category | 用途 | 来源 |
|----------|------|------|
| `fact` | 事实/项目记录 | log_episode |
| `decision` | 决策 | log_episode (category="decision") |
| `preference` | 用户偏好 | log_episode |
| `domain_knowledge` | 领域知识 | extractor |
| `solution` | 解决思路 | log_solution |
| `procedure` | 操作步骤 | log_procedure |
| `correction` | 用户纠正 | log_correction |
| `lesson_learned` | 教训总结 | MemoryFeedbackBridge |
| `kb` | 知识库关联 | KB Promotion |

### 2.3 检索层

| 组件 | 检索路径 | 排序 |
|------|----------|------|
| **HybridSearch** | Chroma 向量 → SQLite BLOB → 仅关键词 → 确定性向量 | decay_score(sim×0.6 + decay×0.2 + imp×0.2) |
| **Reranker** | 可选外部重排模型 | 替换排序 |
| **_adjust_score** | 检索后微调 | solution/correction/lesson_learned/procedural ×1.15；pinned ×1.2；compressed ×0.9 |
| **_cross_entity_discovery** | relations 图扩展关联实体 → 二次检索 | 追加显示，不参与排序 |
| **_proactive_reminders** | 直接 SQL 拉取 solution/pinned/高 importance | 追加显示 |
| **FTS5 关键词** | 全文索引 | 基础分 0.5 + decay |

#### Ebbinghaus 衰减公式

```
score = similarity × 0.6 + decay × 0.2 + importance × 0.2
decay = e^(-age_hours / half_life)
half_life = importance × 720  (importance=1 → 30天半衰期)
```

### 2.4 维护层

| 组件 | 触发 | 职责 |
|------|------|------|
| **SleepAgent** | 空闲/定时 | 语义重复合并（sim>0.9）、冲突检测与解决、衰减处理 |
| **MemoryScheduler** | cron 定时 | 管理定时任务注册（KB Promotion 每日 04:00） |
| **Compressor** | 手动 API | 记忆批量合并（每 10 条→1 条 LLM 摘要）；定时调度已独立关停 |
| **KB Promotion** | 手动/自动阈值 | 记忆要点批量合成 → 知识库 Markdown 文档 |
| **Decay + Cleanup** | 读取时计算 / 定时清理 | importance<0.25 且 >15天 → 自动清理 |
| **Deduplicator** | 写入时 | 四层去重：精确匹配→包含匹配→Jaccard→语义向量 |

### 2.5 进化层（Evolution ↔ Memory 桥梁）

| 组件 | 职责 | 触发 |
|------|------|------|
| **MemoryAwareAnalyzer** | 从 memories 拉取 correction/solution → 聚类 → avoidance_rules + recommendations | Evolution optimize() 每 50 轮 |
| **MemoryFeedbackBridge** | 规则写回 working_principles；方案 pin 住；3+ 次同类纠正 → lesson_learned | 同上 |
| **FeedbackCollector** | 收集用户反馈事件 | 对话中 |
| **CaseDistiller** | 提炼对话为案例 | optimize() |
| **ResponseEvaluator** | 评估回复质量 | 每轮对话 |

---

## 三、核心数据流

### 3.1 对话写入流

```
对话结束
  → MemoryManager.reflect(user_msg, assistant_msg)
    → Reflector.reflect()
      → LLM 生成 JSON ops
        → _apply_op() 路由到具体方法
          → _apply_log_episode()
            → 写入前去重 (deduplicator.is_duplicate)
              → 完全重复 → skip
              → 可更新 → update_memory
              → 不重复 → INSERT
          → _apply_log_solution()
            → INSERT (category="solution", memory_type="procedural", importance=0.8)
          → _apply_log_procedure()
            → INSERT (category="procedure", importance=0.9)
          → _apply_log_correction()
            → INSERT (category="correction", importance=0.85)
          → _apply_update_core() / _apply_upsert_entity() / ...
      → 降级：LLM 失败 → 启发式 → 最小归档
```

### 3.2 上下文构建流

```
Agent 需要上下文
  → MemoryManager.get_context_for_query(query)
    → core.render_for_prompt()           # Core Memory 块
    → HybridSearch.search(query)         # 语义+关键词检索
    → _cross_entity_discovery(memories)  # 实体图扩展
      → 提取 entity_refs → relations 表 → 关联实体
      → 二次检索关联记忆
    → _proactive_reminders(query)        # 主动提醒
      → solution 类记忆
      → pinned 记忆
      → 高 importance 决策
    → return 拼接后的 prompt 片段
```

### 3.3 进化分析流

```
每 50 轮对话
  → EvolutionManager._schedule_optimize()
    → EvolutionOrchestrator.optimize()
      → 现有：personality / subagent / prompt 调优
      → 新增：MemoryAwareAnalyzer.analyze()
        → 拉取 correction 类记忆 → 聚类 → avoidance_rules
        → 拉取 solution 类记忆 → 聚类 → recommendations
      → 新增：MemoryFeedbackBridge.apply_patterns()
        → avoidance_rules → working_principles
        → recommendations → pin memory
        → 3+ 次同类纠正 → lesson_learned
      → eval gate（before/after 对比，可 rollback）
```

---


## 四、能力热力图

```
                        能力强度
Reflector 10 op      ██████████ A+    10种op，三层降级（LLM→启发式→最小归档）
写入去重              ██████████ A     四层去重 + 写入时防重复 + update_episode增量更新
语义检索              ██████████ A     Chroma向量 + FTS5关键词 + Ebbinghaus衰减 + reranker + 排序加权
Core Memory           ██████████ A     4块固定区块 + 行去重 + 自动trim(2048B/30行) + 每用户私有
实体图谱              ██████████ A     entities + relations + FTS5别名 + Jaccard语义合并
遗忘机制              ██████████ A     Ebbinghaus衰减公式 + cleanup(imp<0.25 & age>15d)
关联发现              ████████░ A-    实体图扩展检索 (_cross_entity_discovery)
解决思路学习            ████████░ A-    log_solution op（完整实现：prompt+规则+_apply）
步骤记忆              ████████░ A-    log_procedure op（完整实现：prompt+规则+_apply）
用户纠正记录            ████████░ A-    log_correction op（完整实现：prompt+规则+_apply）
Evolution分析Memory    ████████░ A-    MemoryAwareAnalyzer（correction/solution聚类→规则生成）
Evolution写入Memory    ████████░ A-    MemoryFeedbackBridge（规则→working_principles/pin/lesson）
增量更新              ████████░ A-    update_episode op（key_text匹配→更新，未命中→退化为log_episode）
主动提醒              ████████░ A-    _proactive_reminders（solution/pinned/高importance预注入prompt）
记忆→知识库            ████████░ B+   批量LLM合成Markdown文档（KB Promotion + TurnPublisher）
后台维护              ████████░ B+    SleepAgent(去重/冲突/衰减) + Compressor(手动) + Scheduler(定时)
上下文感知            ███████░░ B      Scene Analyzer(意图) + Working Context(会话画像)
主动预警              █████░░░ C+    基于_proactive_reminders+MemoryAwareAnalyzer，无独立预警引擎

实战验证缺口            ░░░░░░░░░░ ?    全部新功能(Phase A-D/Evolution桥)待生产数据验证
```

## 五、行业对标

| 能力 | TARS | Letta/MemGPT | LangGraph | CrewAI | Mem0/Zep |
|------|------|:---:|:---:|:---:|:---:|
| Core Memory | ✅ 4块 | ✅ | ❌ | ✅ | ❌ |
| Episodic Memory | ✅ 10种op | ✅ | ✅ | ✅ | ✅ |
| 实体知识图谱 | ✅ | ✅ | ❌ | ✅ | ❌ |
| 语义检索 | ✅ Chroma+FTS5 | ✅ | ❌ | ✅ | ✅ |
| Ebbinghaus衰减 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 写入去重 | ✅ 四层 | ✅ | ❌ | ❌ | ✅ |
| 增量更新 | ✅ update_episode | ❌ | ❌ | ❌ | ❌ |
| 记忆→KB晋升 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 解决思路学习 | ✅ log_solution | ❌ | ❌ | ❌ | ❌ |
| 步骤记忆 | ✅ log_procedure | ❌ | ❌ | ❌ | ❌ |
| 用户纠正学习 | ✅ log_correction | ❌ | ❌ | ❌ | ❌ |
| Evolution↔Memory | ✅ 桥梁 | ❌ | ❌ | ❌ | ❌ |
| 主动提醒 | ✅ proactive | ❌ | ❌ | ❌ | ❌ |
| 领域schema | ✅ 港航 | ❌ | ❌ | ❌ | ❌ |
| Sleep Agent | ✅ | ✅ | ❌ | ❌ | ❌ |

---

## 六、配置项

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `TARS_MEMORY_COMPRESSOR` | `false` | Compressor API 开关 |
| `TARS_MEMORY_COMPRESSOR_SCHEDULED` | `false` | Compressor 定时调度（需显式开启） |
| `TARS_KB_PROMOTION` | `false` | KB 晋升自动调度 |
| `TARS_MEMORY_TREE_BUILDER` | `true` | 实体树构建 |
| `TARS_TURN_PUBLISHER` | `false` | 轮次知识发布 |
| `TARS_REFLECTOR_ASYNC` | `true` | Reflector 异步执行 |
| `TARS_MEMORY_ROUTER` | `true` | MemoryRouter 启用 |
| `TARS_SCENE_MODEL` | `gemma4:e2b` | Scene Analyzer 专用模型 |
| `TARS_RELOAD` | `0` | 热重载（易 OOM，建议 0） |

---

## 七、文件索引

```
backend/tars/memory/
  __init__.py            → 模块导出
  manager.py             → MemoryManager (入口)
  reflector.py           → Reflector (10种op)
  core_memory.py         → CoreMemoryManager + tools
  archival.py            → ArchivalManager (写入)
  search.py              → HybridSearch (检索)
  compressor.py          → MemoryCompressor (手动合并)
  scheduler.py           → MemoryScheduler (定时)
  sleep_agent.py         → MemorySleepAgent (后台维护)
  tree_builder.py        → EntityTreeBuilder (实体树)
  working_context.py     → WorkingContextManager
  deduplicator.py        → MemoryDeduplicator (去重)
  decay.py               → Ebbinghaus 衰减
  extractor.py           → LLM/Heuristic/Regex 提取器
  kb_promotion.py        → KB 晋升合成
  turn_knowledge_publisher.py → 知识发布
  router.py              → MemoryRouter
  entity_id.py           → 实体 ID 哈希工具
  domain_schema.py       → 港航实体/关系 schema

backend/tars/evolution/
  memory_analyzer.py     → MemoryAwareAnalyzer (新增)
  memory_feedback_bridge.py → MemoryFeedbackBridge (新增)
  orchestrator.py        → EvolutionOrchestrator (集成)
  manager.py             → EvolutionManager (入口)
```

---

## 八、测试覆盖

| 测试文件 | 用例数 | 覆盖范围 |
|----------|--------|----------|
| `test_memory_v3.py` | 27 | Schema / Core / Decay / Archival / Search / Reflector / Agent |
| `test_memory_management_api.py` | 11 | API CRUD / Merge / Compress / Extract |
| `test_admin_memory_api.py` | 3 | Admin 端点 + 权限 |
| `test_turn_memory_extractor.py` | 4 | 提取器 + Prompt 完整性 |
| `test_tenant_memory_router.py` | 3 | 租户隔离 |
| **合计** | **48** | **全部通过** |

---

*TARS v5.0.5/A3+ · 能力全景图 · 2026-06-16*
