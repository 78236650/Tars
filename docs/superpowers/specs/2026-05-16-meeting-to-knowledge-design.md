---
doc_type: spec
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# 会议纪要入知识库设计

## 核心决策

1. 用户编辑确认后入库（非自动）
2. 摘要用于检索匹配，原文作为证据
3. 固定 collection "会议纪要"，不分类

## 前端操作链路

```
TranscriptionDetail 页面
  → [编辑] 摘要/要点变为可编辑
  → [保存修改] 更新 transcription 记录
  → [确认入库] 弹出预览 → 确认
  → 调用 POST /api/meeting/{id}/approve-to-knowledge
  → 显示 "✅ 已入库" 标记
```

## 后端路由

```
POST /api/meeting/{id}/approve-to-knowledge
Body: { "summary": "编辑后的摘要", "key_points": ["要点1", ...] }
```

流程：
1. 更新 transcription 的 summary/key_points
2. 检查/创建固定 collection "会议纪要"（`meeting_notes_kb`）
3. 构造索引文本：`[会议] {file_name} {date}\n{summary}\n要点: {key_points}`
4. 摘要作为 1 个 chunk 索引（chunk_type=summary）
5. 原文分块索引（chunk_type=transcript，300字/块）
6. 标记 transcription `approved_at` 时间戳 + `knowledge_doc_id`
7. 返回成功

## 知识库存储

固定 collection: `meeting_notes_kb`（系统启动时自动创建）

每次入库生成：
- 摘要 chunk（1个）：语义匹配用
- 原文 chunks（多个）：300字分块，追溯证据

元数据：
```json
{
  "source": "meeting",
  "meeting_id": "xxx",
  "file_name": "周会_20260516",
  "date": "2026-05-16",
  "chunk_type": "summary | transcript"
}
```

## Agent 检索效果

用户问 → 语义匹配摘要 chunk → 返回摘要 + 来源标注 → 可追溯原文

## 数据模型变更

`transcriptions` 表新增：
- `approved_at` TEXT — 入库时间（NULL=未入库）
- `knowledge_doc_id` TEXT — 关联知识库文档 ID

## 文件变更

| 文件 | 操作 |
|------|------|
| `backend/tars/database/base.py` | transcriptions 表加 2 字段 |
| `backend/tars/api/meeting.py` | 新增 POST /{id}/approve-to-knowledge |
| `backend/tars/main.py` | 启动时确保 meeting_notes_kb collection 存在 |
| `frontend/src/components/meeting/TranscriptionDetail.vue` | 编辑模式 + 确认入库按钮 |
| `frontend/src/api/index.ts` | meetingApi 新增 approveToKnowledge 方法 |
