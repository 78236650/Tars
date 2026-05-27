---
doc_type: spec
status: shipped
platform_version: 4.2.0
catalog: docs/superpowers/README.md
---
# 记忆树 v4.2 — 力导向图谱与虚拟滚动

| 字段 | 值 |
|------|-----|
| 状态 | ✅ 已实现（2026-05-19） |
| 基线 | v4.1.4 Memory Entity Tree |
| 日期 | 2026-05-19 |

## 目标

1. **满屏力导向图**：在实体 Tab 内第三视图「图谱」，展示当前租户实体—关系网络，可点击节点查看详情（复用右侧详情区）。
2. **真·虚拟滚动**：实体/谱系左树在扁平化后按行窗口渲染，支撑上千可见行而不卡顿。

## 非目标

- 图谱上编辑/拖拽创建关系
- 跨租户关系隔离（`relations` 表暂无 `tenant_id`，边集按「租户实体集合」过滤）
- 3D 图谱

## 方案

### 图谱 API

`GET /api/memory/tree/graph`

- **nodes**：当前租户记忆中出现的实体（`entity_refs` 聚合），含 `id`、`label`、`type`、`memory_count`
- **edges**：`relations` 中两端均落在上述实体集合的边，`from`、`to`、`predicate`、`confidence`
- **stats**：`node_count`、`edge_count`、`truncated`（边数超限时）

### 前端图谱

- 视图切换：**实体 | 谱系 | 图谱**
- `MemoryEntityForceGraph.vue`：ECharts `graph` + `layout: 'force'`，复用项目已有 `echarts` 依赖
- 节点点击 → `focus-entity` → 右侧加载 `getTreeRelations` 与摘要（无树节点时用 graph 节点 meta）

### 虚拟滚动

- `flattenTree(roots, expandedIds)` → 扁平行
- `MemoryTreeVirtualList.vue`：固定行高 32px，`scroll` 计算 `[start,end)`，仅渲染窗口 + overscan
- 阈值：扁平行 ≥ **40** 时启用（小树仍走原递归，减少复杂度）

## 验收

- [ ] `/memory` → 实体 → 图谱：节点/边可见，点击节点右侧出详情
- [ ] 大树（>120 节点）滚动流畅，DOM 行数 ≈ 视口行数 + overscan
- [ ] `pytest tests/test_memory_tree_api.py::test_tree_graph`
