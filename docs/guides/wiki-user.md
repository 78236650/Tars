# Wiki 使用指南（v4.3.2+）

> LLM Wiki 与 RAG 知识库**并存**：Wiki 适合可编辑的结构化短文；RAG 适合大 PDF/论文长文档检索。

## 和 Memory 的区别

| | Wiki | Memory（Core / Archival） |
|--|------|---------------------------|
| 用途 | 客户/流程/领域**可发布知识页** | 对话偏好、用户画像、会话沉淀 |
| 存储 | `backend/data/wiki/*.md` | SQLite + 向量 |
| Agent 工具 | `read_wiki`、`write_wiki` | `memory`、`core_memory_*` |
| 界面 | 知识库 → **Wiki** Tab | 记忆管理页 |

Reflector **不会**自动写 Wiki；需上传、会议钩子或 Agent 调用 `write_wiki`。

## 用户怎么用

### 1. 界面上看 Wiki

1. 打开 **知识库**
2. 切换到 **Wiki** Tab（与「文档库」并列）
3. 左侧选页面，右侧看 Markdown

若 Tab 为空：尚无页面，见下方写入方式。

### 2. 聊天里让 Agent 写 Wiki

示例提示词：

- 「把刚才讨论的港口流程整理进 wiki，页面名 `port-ops`」
- 「更新 wiki 的 customer-notes，补充今日会议纪要」

Agent 应调用 **`write_wiki`**（`page_name` 用小写英文短横线，如 `customer-notes`），不要只说「已写入」而不调工具。

**Plan / Brainstorm 模式**下也可读写的 Wiki 工具已列入只读白名单。

### 3. 上传文件进 Wiki 或 RAG

上传时可指定路由（API `target`）：

| target | 行为 |
|--------|------|
| `auto` | 按规则 + LLM 判断 Wiki 或 RAG |
| `wiki` | 走 Wiki 编译管线 |
| `rag` | 走传统向量+FTS 入库 |

小文本、纪要类更适合 Wiki；大 PDF 更适合 RAG。

### 4. 会议摘要进 Wiki

会议流程配置允许将摘要发布到 Wiki（见 `meeting` 模块与 Wiki 事件编译器）。

## 纠正类偏好不要进 Wiki

用户说「以后都用中文」「别用某种口吻」→ 用 **self-improving** 技能：

- workspace 内 `self-improving/corrections.md`
- 或 `core_memory_append` → `working_principles`

详见租户技能 `skills/tenants/.../self-improving/SKILL.md`。

## 运维

| 项 | 路径 / 说明 |
|----|-------------|
| Wiki 数据目录 | `backend/data/wiki/`（已在 `.gitignore`，部署时持久化该目录） |
| 索引页 | `index.md`（自动生成，勿用 `write_wiki` 写 `index` 页名） |
| REST | `GET/PUT /api/wiki/...`（管理台与前端 WikiViewer） |

## 设计参考

- [LLM Wiki + RAG 双通路设计](../superpowers/specs/2026-05-25-llm-wiki-rag-dual-path-design.md)
- [实施计划](../superpowers/plans/2026-05-25-llm-wiki-rag-dual-path-plan.md)
