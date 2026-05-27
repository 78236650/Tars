---
doc_type: spec
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# TARS v3.9.0 — 记忆管理页面设计文档

## 概述

新增独立一级页面 `/memory`，提供记忆系统的可视化管理能力，包括人格编辑、近期/长期记忆浏览与操作、自动+手动记忆压缩。

**版本：** v3.9.0
**状态：** ✅ 已实现
**范围：** 前端新页面 + 后端 Memory API + 压缩引擎

---

## 1. 页面结构

**路由：** `/memory`，Sidebar 一级入口
**布局：** 顶部状态栏 + Tab 切换（人格 | 近期记忆 | 长期记忆）

### 1.1 顶部状态栏

- 记忆统计：总数 / 近期数 / 长期数
- 上次压缩时间
- 待压缩徽标（主题记忆数超阈值时显示橙色 badge）
- 手动压缩按钮（触发后显示进度）

### 1.2 人格 Tab

从 `PersonalitySettings.vue` 迁移合并，Settings 中移除该组件。

| 区域 | 内容 |
|------|------|
| 上半区 | 10 维滑块参数 + 4 个预设快选（Professional/Friendly/Creative/Scholar） |
| 中间区 | communication_style 文本框 + behavior_rules 列表编辑 |
| 下半区 | Core Memory persona 块文本编辑器（直接编辑 TARS 自我认知） |

保存时同步写入 settings personality + core_memory_blocks.persona。

### 1.3 近期记忆 Tab

展示最近 7 天的 episodic 记忆，按时间倒序。

- **卡片字段：** 内容摘要（前 100 字）、时间、关联实体标签、importance 分数条
- **操作：** 删除、标记重要（晋升长期）、展开详情
- **顶部：** 搜索框（FTS5）+ 按 category 筛选下拉
- **分页：** 每页 20 条，滚动加载

### 1.4 长期记忆 Tab

展示 importance ≥ 0.6 或 pinned 的记忆，按实体/主题分组。

- **分组折叠：** 按 entity_refs 中的主实体分组，无实体的归入"通用"组
- **操作：** 编辑内容、删除、pin/unpin（保护不被压缩）、多选合并
- **多选合并：** 选中 2+ 条 → 点击"合并压缩" → 调用 LLM 生成摘要 → 预览确认 → 替换原记忆

---

## 2. 后端 API 设计

新增路由组 `/api/memory/`，挂载到现有 FastAPI app。

### 2.1 端点列表

```
GET    /api/memory/stats                    # 统计概览
GET    /api/memory/core                     # 获取全部 core memory blocks
PUT    /api/memory/core/{block}             # 更新指定 core block
GET    /api/memory/recent?page=&q=&cat=     # 近期记忆列表（7天内）
GET    /api/memory/longterm?page=&group_by= # 长期记忆列表（分组）
GET    /api/memory/{id}                     # 单条记忆详情
PUT    /api/memory/{id}                     # 编辑记忆内容
DELETE /api/memory/{id}                     # 删除记忆
POST   /api/memory/{id}/pin                 # 标记保护
POST   /api/memory/{id}/promote             # 晋升为长期记忆
POST   /api/memory/compress                 # 手动触发全局压缩
POST   /api/memory/merge                    # 手动合并指定记忆
GET    /api/memory/compress/status          # 压缩状态查询
```

### 2.2 数据模型扩展

`memories` 表新增字段：

```sql
ALTER TABLE memories ADD COLUMN pinned INTEGER DEFAULT 0;
ALTER TABLE memories ADD COLUMN compressed_from TEXT DEFAULT NULL;  -- JSON: 被合并的原始 memory IDs
ALTER TABLE memories ADD COLUMN memory_type TEXT DEFAULT 'episodic'; -- episodic | longterm | compressed
```

---

## 3. 压缩引擎设计

### 3.1 压缩策略：摘要合并 + 层级归档

```
[多条同主题记忆] → LLM 摘要合并 → 1条压缩记忆(importance取max)
                                    ↓
                        importance ≥ 0.6 → 标记为 longterm
                        importance < 0.6 → 保留为 episodic（继续衰减）
```

### 3.2 触发机制（混合模式）

| 触发方式 | 条件 | 行为 |
|----------|------|------|
| 阈值触发 | 同一实体关联记忆 > 10 条 | Reflector 写入后检查，异步触发该实体的压缩 |
| 定时兜底 | 每日 03:00 | 扫描所有实体，压缩超阈值的；清理 importance < 0.25 且 age > 15d 的 |
| 手动触发 | 用户点击按钮 | 立即执行全局压缩，返回压缩报告 |

### 3.3 压缩流程

```python
async def compress_entity_memories(entity_id, memories):
    # 1. 按时间排序，取同实体下 importance < 0.6 的非 pinned 记忆
    # 2. 分批（每批 ≤ 10 条）送 LLM 生成摘要
    # 3. 创建新 compressed 记忆（importance = max(batch), compressed_from = [ids]）
    # 4. 删除原始记忆
    # 5. 更新 embedding
```

### 3.4 LLM Prompt 模板

```
你是记忆压缩器。将以下多条记忆合并为一条精炼摘要：
- 保留关键事实、决策、偏好
- 去除重复和琐碎细节
- 保持时间线顺序感
- 输出不超过 200 字
```

---

## 4. 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 前端框架 | Vue 3 + Composition API | 项目现有技术栈 |
| UI 组件 | Tailwind CSS（手写） | 项目现有风格，无额外组件库 |
| 后端框架 | FastAPI Router | 项目现有，新增 router 挂载 |
| 后台调度 | asyncio background task + APScheduler | 轻量，不引入 Celery；APScheduler 做定时，asyncio task 做即时压缩 |
| 压缩 LLM | 复用当前配置的模型（通过 settings.current_model） | 不额外引入模型依赖 |
| 数据库 | SQLite（现有） | 新增字段 + 索引即可 |
| 状态通知 | SSE 或轮询 | 压缩进度推送，优先 SSE（项目已有 streaming 基础） |

---

## 5. 文件结构

```
backend/tars/api/memory.py              # Memory API 路由
backend/tars/memory/compressor.py       # 压缩引擎
backend/tars/memory/scheduler.py        # 定时任务调度

frontend/src/views/MemoryView.vue       # 记忆管理页面（Tab 容器）
frontend/src/components/memory/
  PersonalityTab.vue                    # 人格 Tab（从 PersonalitySettings 迁移）
  RecentMemoryTab.vue                   # 近期记忆 Tab
  LongtermMemoryTab.vue                 # 长期记忆 Tab
  MemoryCard.vue                        # 记忆卡片组件
  CompressDialog.vue                    # 压缩确认/进度对话框
  MergePreviewDialog.vue                # 手动合并预览对话框
```

---

## 6. 实施顺序

1. DB migration：新增字段 + 索引
2. 后端 Memory API（CRUD + stats）
3. 压缩引擎 + 调度器
4. 前端 MemoryView + 路由 + Sidebar 入口
5. 人格 Tab（迁移 PersonalitySettings）
6. 近期记忆 Tab
7. 长期记忆 Tab + 合并功能
8. 压缩状态通知 + 手动触发
9. 移除旧 PersonalitySettings 路由

---

## 7. 不在本期范围

- 实体图谱可视化（二期）
- 记忆导入/导出
- 跨租户记忆迁移
- Working Context 编辑（会话级，不适合手动管理）
