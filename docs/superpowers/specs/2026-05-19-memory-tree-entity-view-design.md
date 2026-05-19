# TARS 记忆树 — 实体视图设计规格

## 元信息

| 项 | 值 |
|----|-----|
| 日期 | 2026-05-19 |
| 版本 | v1.1 |
| 状态 | ✅ Phase 1–3 已实现（2026-05-19） |
| 依赖 | v3.9 记忆管理页、v2.2 实体/关系表、`entity_refs` / `compressed_from` |
| 前置规格 | `2026-05-16-memory-management-ui-design.md`（二期「实体图谱」的落地首版） |

---

## 1. 概述

在 `/memory` 记忆菜单新增 **「实体」Tab**（内部 key: `tree`），以 **实体为中心** 展示当前用户（租户）的记忆结构：每个实体是一棵子树的根，其下挂载关联记忆；系统级「核心记忆」与「未归类」作为特殊实体分支；选中实体时可查看 `relations` 表中的关系边。

**默认视图：实体树**（非资产树、非纯谱系树）。谱系视图作为 Tab 内二级切换，**v4.2+ 可选**。

### 已确认产品决策（2026-05-19）

| 决策项 | 结论 |
|--------|------|
| 与现有 Tab 关系 | **保留** 人格 / 近期 / 长期 / 全部 / 管理；**新增**「实体」Tab |
| Tab 显示名 | **实体**（内部 key: `tree`） |
| 主界面形态 | **B 实体树**（资源管理器式） |
| 关系展示 | **轻量 C**：选中实体后右侧短列表（`relations`），**不做** 首屏满屏力导向图 |
| 列表 Tab | 继续承担「搜一条、改一条」 |
| 行业参考 | Mem0 列表为主 + 移除 Graph Tab；Letta Block 为主；Obsidian 大纲管理 + 图谱探索 |

**设计原则：**

- **只读为主**：树上不直接编辑；操作在右侧详情面板复用 `MemoryCard` 能力
- **服务端组树**：前端不做大规模 join，避免 N+1
- **与列表 Tab 互补**：树负责「我在记谁/什么」；近期/长期 Tab 负责批量操作

---

## 2. 目标与非目标

### 2.1 目标

| # | 目标 | 成功标准 |
|---|------|----------|
| G1 | 用户 10 秒内理解「Agent 围绕哪些实体在积累记忆」 | 实体数、每实体记忆条数可见 |
| G2 | 从实体定位到具体记忆并操作 | 点击叶子 → 详情 → 删除/晋升/pin ≤ 3 次点击 |
| G3 | 看见实体间关系（不画全图） | 选中实体展示 relations 入/出边 |
| G4 | 解释压缩血缘 | 叶子标记 `compressed`，详情展示 `compressed_from` |
| G5 | Admin 查看指定用户实体树 | 与 Admin Tab 共用 `user_id` 选择器 |

### 2.2 非目标（本期）

- 力导向知识图谱、画布拖拽改关系
- 在树上新建/合并实体（走 Reflector / 对话）
- 跨租户实体对比
- Working Context 可视化
- 自动实体消歧 UI（aliases 合并流程仅展示，不提供合并向导）

---

## 3. 用户场景

### 3.1 终端用户

1. **「Agent 到底记住了关于我和项目的什么？」**  
   展开 `person:*`、`project:*`，按长期/近期浏览。

2. **「某项目下记忆太多，想清理」**  
   在实体节点看到计数 badge → 跳转长期 Tab 并带 `entity` 筛选（v1.1）。

3. **「这条摘要是怎么来的？」**  
   点开 `memory_type=compressed` 叶子，详情展示源记忆 ID 列表。

4. **「Alice 和 TARS 项目什么关系？」**  
   选中 Alice，侧栏关系区显示 `works_on → TARS`（来自 `relations`）。

### 3.2 管理员

5. **用户反馈「记混了」**  
   Admin 选用户 → 实体 Tab 看是否实体爆炸、未归类堆积、核心块为空。

---

## 4. 信息架构

### 4.1 树层级（默认展开策略）

```
根: 我的记忆
├── [系统] 核心记忆                    # id: __core__
│   ├── persona
│   ├── user_profile
│   ├── project_context
│   └── working_principles
├── 人物                               # entity_type: person
│   ├── Alice (person:a1b2c3d4)       # entity 节点
│   │   ├── 长期记忆 (3)
│   │   ├── 近期记忆 (5)
│   │   └── 压缩记忆 (1)
│   └── ...
├── 项目                               # project
├── 概念                               # concept
├── 决策                               # decision
├── 其他                               # 未知 type
├── 未归类                             # id: __orphan__
│   └── (无 entity_refs 的记忆)
└── (空时隐藏)
```

**实体节点排序：** `importance`（entities 表或聚合 max）降序 → `memory_count` 降序 → `name` 字母序。

**类型分组排序：** person → project → concept → decision → other → `__core__` 置顶 → `__orphan__` 置底。

### 4.2 实体下第二层：按 `memory_type` 分桶

与现有 Tab 语义对齐，避免用户认知冲突：

| 桶 key | 条件 | 标签 |
|--------|------|------|
| `longterm` | `memory_type=longterm` 或 (`importance≥0.6` 且非 compressed) | 长期 |
| `recent` | 7 天内 episodic | 近期 |
| `compressed` | `memory_type=compressed` | 压缩 |

桶内叶子排序：`pinned` > `importance` > `event_time`/`created_at` 降序。

每桶默认最多 **30** 条，超出显示 `+N 条更多` 节点，点击跳转「全部记忆」Tab 并带筛选。

### 4.3 多实体关联（共现）

- **树归属：** 记忆仅挂在 `entity_refs[0]`（主实体）下
- **叶子展示：** 副实体以 tag 展示（`entity_refs[1..]`）
- **详情面板：** 「共现实体」列表，可点击聚焦到对应实体节点（前端路由树 focus）

### 4.4 特殊节点

| 节点 id | 含义 |
|---------|------|
| `__core__` | 4 块 Core Memory，子节点为 block 名，非 DB memory |
| `__orphan__` | `entity_refs` 为空、`[]` 或解析失败的记忆 |
| `__type:{type}`` | 类型分组（虚拟） |
| `{entity_id}` | 如 `person:a1b2c3d4`，来自 `compute_entity_id` |

---

## 5. 实体解析规则

### 5.1 `entity_refs` 存储格式（现状）

Reflector 写入为 **实体 ID 字符串列表**，如 `["person:a1b2c3d4", "project:e5f6g7h8"]`。  
历史数据可能为 **dict** `{ "name": "Alice", "type": "person" }` 或纯字符串显示名。

### 5.2 显示名解析（优先级）

1. `entities` 表：`SELECT name, type, aliases FROM entities WHERE id = ?`
2. 解析 ID：`person:hash` → 若 memories 中 dict 含 `name`，用该 name
3. 兜底：显示 `{type}` + ID 短码，如 `人物 · a1b2c3d4`

### 5.3 实体注册表同步

组树时：

1. 从 `memories` 聚合所有 `entity_refs` → 实体 ID 集合
2. LEFT JOIN `entities` 补全名称；**无 rows 的 ID 仍展示**（幽灵实体）
3. `stats.ghost_entity_count` 供 Admin 发现「有记忆无注册」问题

### 5.4 关系边

```sql
SELECT from_entity, to_entity, predicate, confidence, created_at
FROM relations
WHERE from_entity = ? OR to_entity = ?
ORDER BY confidence DESC
```

不在树主干画边，仅在 **实体选中时** 右侧「关系」区展示。

---

## 6. API 设计

### 6.1 端点

```
GET /api/memory/tree
```

**Query 参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `view` | string | `entity` | 固定 `entity`（预留 `provenance`） |
| `max_per_bucket` | int | 30 | 每实体每桶上限 |
| `include_core` | bool | true | 是否包含 `__core__` 枝 |
| `include_orphan` | bool | true | 是否包含未归类 |
| `include_relations` | bool | false | 为 true 时每实体带 relations（重；默认选中后再请求） |
| `user_id` | string | - | Admin 查看指定租户 |

**Headers：** 与现有 memory API 一致（`X-Tenant-Id`, `X-User-Role`）。

### 6.2 响应结构

```json
{
  "view": "entity",
  "tenant_id": "user_123",
  "stats": {
    "entity_count": 12,
    "memory_count": 87,
    "orphan_count": 3,
    "ghost_entity_count": 2,
    "relation_count": 5,
    "core_filled_blocks": 3
  },
  "nodes": [
    {
      "id": "__core__",
      "kind": "system",
      "label": "核心记忆",
      "meta": { "filled_blocks": 3, "total_blocks": 4 },
      "children": [
        {
          "id": "core:persona",
          "kind": "core_block",
          "label": "Persona",
          "meta": { "char_count": 420, "line_count": 8 },
          "children": []
        }
      ]
    },
    {
      "id": "__type:person",
      "kind": "type_group",
      "label": "人物",
      "meta": { "entity_count": 2 },
      "children": [
        {
          "id": "person:a1b2c3d4",
          "kind": "entity",
          "label": "Alice",
          "meta": {
            "type": "person",
            "memory_count": 8,
            "longterm_count": 3,
            "recent_count": 4,
            "compressed_count": 1,
            "max_importance": 0.85,
            "is_ghost": false
          },
          "children": [
            {
              "id": "person:a1b2c3d4:bucket:longterm",
              "kind": "bucket",
              "label": "长期记忆",
              "meta": { "count": 3, "truncated": false },
              "children": [
                {
                  "id": "mem-uuid-1",
                  "kind": "memory",
                  "label": "用户偏好使用 TypeScript…",
                  "meta": {
                    "memory_type": "longterm",
                    "importance": 0.8,
                    "pinned": true,
                    "category": "user_preference",
                    "created_at": "2026-05-18T10:00:00+08:00",
                    "co_entities": ["project:e5f6g7h8"]
                  },
                  "children": []
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

### 6.3 实体关系（按需加载）

```
GET /api/memory/tree/relations?entity_id=person:a1b2c3d4
```

```json
{
  "entity_id": "person:a1b2c3d4",
  "outgoing": [
    { "to_entity": "project:e5f6g7h8", "to_label": "TARS", "predicate": "works_on", "confidence": 0.9 }
  ],
  "incoming": []
}
```

### 6.4 搜索定位

```
GET /api/memory/tree/search?q=typescript&limit=20
```

返回扁平命中列表 + `path`（节点 id 数组），供前端 `expandPath(path)`。

### 6.5 权限

- 读树：与 `GET /api/memory/recent` 相同（`MemoryPermission.filter_readable`）
- Admin `user_id`：仅 `role=admin`
- `relations`：只读，租户隔离

---

## 7. 后端实现

### 7.1 模块

```
backend/tars/memory/tree_builder.py    # EntityTreeBuilder
backend/tars/api/memory.py             # 挂载 /tree, /tree/relations, /tree/search
backend/tests/test_memory_tree_api.py
```

### 7.2 组树算法（伪代码）

```python
class EntityTreeBuilder:
    def build(self, tenant_id: str, max_per_bucket: int = 30) -> dict:
        memories = self.db.list_memories_for_tree(tenant_id)  # 单次查询，必要字段
        entity_index = self._index_by_primary_entity(memories)
        entity_meta = self._load_entity_meta(entity_index.keys())
        type_groups = self._group_entities_by_type(entity_index, entity_meta)
        nodes = []
        if include_core:
            nodes.append(self._build_core_branch(tenant_id))
        nodes.extend(self._build_type_branches(type_groups, max_per_bucket))
        if include_orphan:
            nodes.append(self._build_orphan_branch(...))
        return {"nodes": nodes, "stats": self._compute_stats(...)}
```

**性能：**

- 单次 SQL 拉取租户记忆（上限 5000，与 export 一致）
- 内存分组 O(n)
- 目标 P95 < 1.5s @ 2000 条

### 7.3 DB 辅助查询（可选优化）

```sql
-- 实体记忆计数（加速 stats）
SELECT entity_refs, COUNT(*) FROM memories
WHERE tenant_id = ? AND entity_refs IS NOT NULL
GROUP BY entity_refs;  -- 注意 JSON 需应用层解析
```

首期应用层解析即可；数据量大再加物化视图或 `entity_id` 冗余列（**不在本期**）。

---

## 8. 前端设计

### 8.1 组件

```
frontend/src/components/memory/MemoryTreeTab.vue      # Tab 容器
frontend/src/components/memory/MemoryTreePanel.vue    # 左树
frontend/src/components/memory/MemoryEntityDetail.vue # 右详情+关系
frontend/src/components/memory/MemoryTreeNode.vue     # 递归节点
```

`MemoryView.vue` tabs 增加：

```ts
{ key: 'tree', label: t('memory.tab.entity') }  // 显示名：「实体」
```

建议插入位置：`longterm` 与 `all` 之间。

### 8.2 布局

| 视口 | 布局 |
|------|------|
| ≥1024px | 左 40% 树 + 右 60% 详情 |
| <1024px | 全屏树，点击实体/叶子 bottom sheet 详情 |

### 8.3 节点视觉

| kind | 图标 | 交互 |
|------|------|------|
| `type_group` | 文件夹 | 展开/折叠 |
| `entity` | 按 type 区分（人/项目/灯泡/勾选） | 选中高亮，加载 relations |
| `bucket` | 层叠 | 展开叶子 |
| `memory` | 文档 | 打开详情 |
| `core_block` | 芯片 | 跳转人格 Tab 对应区块（v1.1） |
| `system` | 齿轮 | - |

**Badge：** 实体节点显示总记忆数；桶显示 `(n)`；pinned 叶子显示📌。

### 8.4 顶栏工具

- 搜索框（防抖 300ms → `/tree/search`）
- 全部展开 / 全部折叠
- 刷新
- 视图切换（v1.1）：`实体` | `谱系`（仅 compressed 链）

### 8.5 详情面板内容

**实体选中：**

- 名称、type、ID、aliases（若有）
- 统计：长期/近期/压缩数量
- 关系列表（`/tree/relations`）
- 快捷：「在长期记忆中管理」

**记忆叶子选中：**

- 复用 `MemoryCard` 展开态
- `compressed_from` 列表（可点击已删除则灰显）
- 共现实体 tags

### 8.6 状态

```ts
interface MemoryTreeState {
  nodes: TreeNode[]
  stats: MemoryTreeStats
  selectedId: string | null
  expandedIds: Set<string>
  searchHits: SearchHit[]
  relations: EntityRelations | null
  loading: boolean
}
```

---

## 9. i18n 键（草案）

```
memory.tab.entity = 实体
memory.tree.title = 记忆实体结构
memory.tree.searchPlaceholder = 搜索记忆或实体…
memory.tree.empty = 还没有关联到实体的记忆
memory.tree.orphan = 未归类
memory.tree.core = 核心记忆
memory.tree.ghostHint = 该实体尚未在实体库注册
memory.tree.bucket.longterm = 长期记忆
memory.tree.bucket.recent = 近期记忆
memory.tree.bucket.compressed = 压缩记忆
memory.tree.more = 还有 {n} 条
memory.tree.relations = 实体关系
memory.tree.coEntities = 共现实体
```

---

## 10. 实施计划

### Phase 1 — MVP（约 5 天）

- [ ] `EntityTreeBuilder` + `GET /api/memory/tree`
- [ ] `MemoryTreeTab` 基础树 + 实体/记忆详情
- [ ] 接入 `MemoryView` Tab
- [ ] 单测：空数据、单实体、orphan、core、截断

### Phase 2 — 增强（约 3 天）

- [ ] `/tree/search` + 路径展开
- [ ] `/tree/relations` + 详情关系区
- [ ] Admin 用户选择联动
- [ ] 跳转长期 Tab 带 entity 筛选

### Phase 3 — 谱系视图（约 2 天，可拆 v4.2）

- [ ] `view=provenance` 仅压缩链
- [ ] Tab 内 Segmented 切换

---

## 11. 测试要点

| 用例 | 预期 |
|------|------|
| 无记忆 | 仅 `__core__` + 空态文案 |
| 仅 orphan | `__orphan__` 有子，无类型分组 |
| 多实体共现 | 记忆只在主实体下，co_entities 在 meta |
| >30 条/桶 | `truncated: true` + more 节点 |
| 非 admin 带 user_id | 403 |
| compressed 源已删 | 详情显示「已归档」 |

---

## 12. 风险

| 风险 | 缓解 |
|------|------|
| `entity_refs` 格式不一致 | 统一 normalize 函数，单测覆盖 dict/string |
| 幽灵实体过多 | stats 暴露 + Admin 文档说明 |
| 大树卡顿 | 默认折叠类型分组；虚拟列表（>200 节点时） |
| relations 表为空 | 关系区空态，不报错 |

---

## 13. 与路线图关系

- 兑现 v3.9 规格 **「实体图谱可视化（二期）」** 的 **树形首版**
- 图谱画布（力导向）列为 **v4.2+** 独立项，复用本 API 的 `entity_id` / `relations`

---

## 14. 评审检查清单

- [x] 默认实体视图层级是否符合产品预期？— **是**
- [x] 主实体归属（`entity_refs[0]`）是否可接受？— **是**
- [x] Tab 显示名：「实体」— **已确认**
- [x] Phase 1 范围是否同意上线？— **是（B + 轻量 C，无首屏图谱）**

---

## 15. 实施计划

见 [`docs/superpowers/plans/2026-05-19-memory-tree-entity-view-plan.md`](../plans/2026-05-19-memory-tree-entity-view-plan.md)

---

*文档版本: v1.1 | 更新: 2026-05-19 | 状态: 已确认*
