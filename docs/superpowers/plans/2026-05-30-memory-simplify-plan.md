# PortMeta Agent 记忆系统精简方案

> 日期：2026-05-30  
> 版本：v4.4.0 记忆精简  
> 原则：企业用户只需要"存得进、搜得出、用得着"

---

## 一、当前 vs 目标

### 当前记忆系统（过度设计）

```
memory/
├── manager.py          # 记忆管理器
├── core_memory.py      # 4 块固定区块
├── archival.py         # 长期记忆 CRUD
├── search.py           # Embedding + FTS5 + CJK LIKE
├── decay.py            # Ebbinghaus 衰减算法
├── reflector.py        # 每轮对话后异步提取
├── entity_tree.py      # 实体树构建
├── entity_builder.py   # 实体关系提取
├── graph.py            # 知识图谱
db/
├── 10+ 张表            # entities, entity_aliases, memory_entity_links,
│                       #   memory_relations, memory_tree_nodes,
│                       #   memory_tree_bindings, kb_promotion, ...
frontend/
├── MemoryView.vue      # 7 个 tab
├── PersonalityTab.vue
├── RecentMemoryTab.vue
├── LongtermMemoryTab.vue
├── MemoryTreeTab.vue   # 实体树 + 图谱
├── EntityDetailDialog.vue
└── MergePreviewDialog.vue
```

### 目标记忆系统（企业实用）

```
memory/
├── store.py            # 记忆存取（CRUD + 语义搜索 + FTS5）
├── extractor.py        # 会话后简单的关键词/偏好提取
└── core.py             # 用户偏好（减少为 2 块）
db/
├── memories 表         # 保留
├── core_memory 表      # 保留
frontend/
├── MemoryView.vue      # 2 个 tab
├── MemoryList.vue      # 记忆列表 + 搜索
└── MemorySettings.vue  # 用户偏好
```

---

## 二、砍掉清单

### 后端删除

| 文件/模块 | 原因 |
|------|------|
| `memory/decay.py` | Ebbinghaus — 企业记忆不该遗忘 |
| `memory/reflector.py` | 异步提取增加延迟，用户无感 |
| `memory/entity_tree.py` | 实体树 — 企业用户不需要 |
| `memory/entity_builder.py` | 同上 |
| `memory/graph.py` | 知识图谱 — 学术概念 |
| `memory/archival.py` | 合并到 store.py |
| `memory/core_memory.py` | 简化后合并到 core.py |
| `memory/search.py` | 合并到 store.py |

### 数据库表删除

```sql
DROP TABLE IF EXISTS entities;
DROP TABLE IF EXISTS entity_aliases;
DROP TABLE IF EXISTS memory_entity_links;
DROP TABLE IF EXISTS memory_relations;
DROP TABLE IF EXISTS memory_tree_nodes;
DROP TABLE IF EXISTS memory_tree_bindings;
DROP TABLE IF EXISTS kb_promotion_groups;
```

### 数据库表保留+简化

```sql
-- 主记忆表（去掉无用字段）
ALTER TABLE memories DROP COLUMN entity_refs;
ALTER TABLE memories DROP COLUMN compressed_from;
ALTER TABLE memories DROP COLUMN promotion_group_id;
ALTER TABLE memories DROP COLUMN kb_doc_id;
ALTER TABLE memories DROP COLUMN kb_promotion_status;

-- 用户偏好表（减少为 2 块）
-- core_memory: 只保留 user_preferences, project_context
DELETE FROM core_memory WHERE key NOT IN ('user_preferences', 'project_context');
```

### 前端删除

| 文件 | 原因 |
|------|------|
| `MemoryTreeTab.vue` | 实体树/图谱视图 |
| `EntityDetailDialog.vue` | 实体详情弹窗 |
| `LongtermMemoryTab.vue` | 合并到 MemoryList.vue |
| `MergePreviewDialog.vue` | 记忆合并预览 |
| `PersonalityTab.vue` | 已移到末尾，直接删除 |
| `MemoryView.vue` 中 5/7 个 tab | 只保留 list + tree → 改为 list + settings |

---

## 三、保留+增强

### 记忆存储（`store.py`，~250 行）

```
store.py:
  add(content, category, tenant_id) → Memory
  search(query, tenant_id) → List[Memory]   # 语义 + FTS5 双路
  list(tenant_id, page, category) → List[Memory]
  delete(memory_id)
  get_preferences(tenant_id) → dict
  set_preferences(tenant_id, key, value)
```

### 用户偏好（`core.py`，~60 行）

```
core.py:
  get_user_preferences(tenant_id) → {"language": "zh", "detail_level": "concise", ...}
  set_user_preference(tenant_id, key, value)
  get_project_context(tenant_id) → {"project": "PortMeta", "role": "调度员", ...}
```

### 简单提取（`extractor.py`，~80 行）

```
extractor.py:
  extract_from_conversation(user_msg, assistant_msg)
    → 提取: 用户偏好（规则匹配，不调 LLM）
    → 例如: "记住，我喜欢简洁回答" → set_preference("style", "concise")
    → 例如: "我们用的是 Oracle 数据库" → set_preference("database", "Oracle")
```

### 前端（2 个 tab）

```
┌─────────────────────────────────────────┐
│  [记忆列表]  [偏好设置]                   │
├─────────────────────────────────────────┤
│  🔍 搜索记忆...                          │
│                                         │
│  近期记忆                         分类 ▼ │
│  ┌─────────────────────────────────────┐ │
│  │ 📌 用户偏好简洁回答                    │ │
│  │    2 小时前 · user_preference       │ │
│  ├─────────────────────────────────────┤ │
│  │ 📄 元洪码头岸桥 QC-7 上月故障        │ │
│  │    昨天 · project_record            │ │
│  ├─────────────────────────────────────┤ │
│  │ 💬 客户要求报告含堆场利用率图表       │ │
│  │    3 天前 · important_decision      │ │
│  └─────────────────────────────────────┘ │
│                          [加载更多]      │
└─────────────────────────────────────────┘
```

---

## 四、实施步骤

### Task 1: 后端精简（1 天）

- [ ] 删除 7 个文件：decay.py、reflector.py、entity_tree.py、entity_builder.py、graph.py、archival.py、core_memory.py
- [ ] 创建 `store.py`：合并 CRUD + 搜索
- [ ] 创建 `core.py`：简化偏好管理
- [ ] 创建 `extractor.py`：规则匹配提取
- [ ] 更新 `manager.py`：指向新 store
- [ ] 数据库迁移：删除 7 张表，清理无用字段
- [ ] 更新 `__init__.py` exports

### Task 2: 前端精简（0.5 天）

- [ ] 删除 4 个组件：MemoryTreeTab、EntityDetailDialog、LongtermMemoryTab、MergePreviewDialog、PersonalityTab
- [ ] 创建 `MemoryList.vue`：搜索 + 分类过滤 + 分页
- [ ] 创建 `MemorySettings.vue`：用户偏好表单
- [ ] 简化 `MemoryView.vue`：2 个 tab

### Task 3: 清理调用方（0.5 天）

- [ ] `agent.py` 中移除 Reflector 调用
- [ ] `main.py` 中移除 startup 的实体树初始化
- [ ] API 路由清理：移除 entity/tree/graph 相关端点
- [ ] 全量测试回归

---

## 五、收益

| 指标 | 当前 | 精简后 | 变化 |
|------|:---:|:---:|------|
| 后端记忆代码 | ~2500 行 | ~400 行 | **-84%** |
| 数据库表 | 10+ 张 | 3 张 | -70% |
| 前端组件 | 7 个 | 3 个 | -57% |
| 用户理解成本 | 需要培训 | 开箱即用 | — |
| 维护负担 | 高 | 低 | — |
| 核心功能（存+搜） | ✅ | ✅ | 不变 |

---

## 六、风险

| 风险 | 对策 |
|------|------|
| 砍掉 Entity Tree 后用户有需求 | 需要时再加回来，先轻量化上线 |
| 删除 Reflector 后记忆提取需要替代 | extractor.py 规则匹配覆盖 80% 场景 |
| 数据库迁移导致旧数据丢失 | 先备份 `backend/data/tars.db` |
