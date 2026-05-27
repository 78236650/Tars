---
name: self-improving
description: 记录用户对回答风格、项目偏好、流程的纠正，并在租户 workspace 内持久化；可推广到 Wiki 或 memory。勿使用 ~/ 或工作区外路径。
permissions:
  - file_read
  - file_write
triggers:
  - "记住"
  - "纠正"
  - "以后都"
  - "别再用"
  - "偏好"
  - "习惯"
  - "correction"
  - "preference"
  - "self-improving"
priority: 55
---

# Self-Improving — 纠正与偏好

## 路径规则（必须遵守）

- **禁止** `~/`、`/Users/...`、Docker 容器外路径；TARS 只允许 **当前租户 workspace** 内的相对路径。
- 纠正日志固定文件：`self-improving/corrections.md`（相对 workspace 根目录）。
- 列出目录用 `file_list`，`path` 填 `self-improving` 或 `.`，**不要**填 `~/self-improving`。

## 写入纠正

1. 若不确定文件是否存在：先用 `file` 读 `self-improving/corrections.md`；不存在则 `file_write` 创建（`mode: write`）并写入标题 `# Corrections Log`。
2. 追加新条目：`file_write`，`path: self-improving/corrections.md`，`mode: append`。
3. 保留最近约 **50** 条；超出时删最旧段落或归档到 `self-improving/archive-YYYY-MM.md`（仍在 workspace 内）。

## 条目格式

```markdown
## 2026-05-28

### 14:32 — Code style
- **Correction:** "Use 2-space indentation, not 4"
- **Context:** Editing TypeScript file
- **Count:** 1
```

字段：**Correction**（用户原话）、**Context**（触发场景）、**Count**（同类次数；≥3 可考虑推广）。

## 推广去向

| 类型 | 工具 | 说明 |
|------|------|------|
| 个人/对话偏好 | `memory` | 简短、可检索的偏好句 |
| 客户/流程/领域知识 | `write_wiki` | `page_name` 用小写短横线（如 `customer-notes`），勿用 `index` |
| 项目专属说明 | `file_write` | 如 `self-improving/projects/{name}.md` |

写 Wiki 时必须调用 **`write_wiki`** 并传入完整 Markdown；不要口头声称已写入。

## 示例条目

```markdown
## 2026-02-19

### 16:15 — Communication
- **Correction:** "Don't start responses with 'Great question!'"
- **Context:** Chat response
- **Count:** 3 → **PROMOTED** (memory / wiki)
```

## 不要做的事

- 不要调用 `bi_query` 除非用户明确要查 BI 数据（与本技能无关）。
- 不要用 `file_list` / `file_write` 访问 workspace 外的 `self-improving` 目录。
