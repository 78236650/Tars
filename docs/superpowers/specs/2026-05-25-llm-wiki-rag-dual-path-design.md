# v4.3.2 LLM Wiki + RAG 双路径知识系统设计

## 概述

引入 Karpathy LLM Wiki 模式，与现有 RAG 管线并存，形成双路径知识系统：
- **Wiki 路径**（write-time 编译）：小文件、会议纪要、碎片知识 → LLM 增量编译为结构化 Markdown
- **RAG 路径**（query-time 检索）：大文件、论文、PDF/Word → 切片+向量+FTS5 混合检索

两者通过统一入口接入，自动路由 + 用户可覆盖。

## 设计决策

| 决策点 | 方案 |
|--------|------|
| 双路径 | Wiki（write-time 编译）+ RAG（query-time 检索）并存 |
| Wiki 适用 | 小文件、会议纪要、碎片知识、频繁更新的内容 |
| RAG 适用 | 大文件、论文、PDF/Word、一次解析长期存档 |
| 编译触发 | 事件驱动 |
| Wiki 结构 | 全平铺 + index.md，LLM 自由组织 |
| 入口 | 统一上传，自动路由 + 用户可覆盖 |
| 路由规则 | 规则优先 + LLM 兜底 |
| Agent 使用 wiki | index 摘要注入 prompt + read_wiki 工具按需读取 |
| Agent 记忆/技能 | 复用现有 Memory 模块，不在 wiki 中单独建区 |

## 架构

```
┌─────────────────────────────────────────────────┐
│                 统一上传入口                       │
│         POST /api/knowledge/upload               │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│              路由判断层 (Router)                   │
│  规则优先 → LLM 兜底 → 用户可覆盖                  │
└────────┬────────────────────────┬───────────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐    ┌─────────────────────────┐
│   Wiki 管线      │    │      RAG 管线            │
│                 │    │  （现有 Knowledge 模块）    │
│  事件驱动编译    │    │                           │
│  LLM 增量整理    │    │  切片 → 向量化 → 索引      │
│  输出 Markdown   │    │  Enricher 语义增强        │
└────────┬────────┘    └────────────┬─────────────┘
         │                          │
         ▼                          ▼
┌─────────────────┐    ┌─────────────────────────┐
│  wiki/ 目录      │    │  SQLite + FTS5 + Vector  │
│  index.md       │    │  （现有存储）              │
│  page-*.md      │    │                           │
└─────────────────┘    └─────────────────────────┘
```

## Wiki 管线详细设计

### 存储结构

```
data/wiki/
├── index.md          ← 全局索引（标题 + 一句话摘要 + 链接）
├── vessel-scheduling.md
├── port-operations.md
├── customer-notes.md
└── ...               ← LLM 自由创建/合并/拆分页面
```

不预设分类目录，LLM 根据内容自行组织页面结构。index.md 由 LLM 在每次编译后自动更新。

### 编译触发事件

| 事件 | 触发源 | 时效 |
|------|--------|------|
| 会议结束 | Meeting ASR 模块发出 `meeting_ended` 事件 | 秒级 |
| 小文件上传 | 路由判断后分发到 Wiki 管线 | 分钟级 |
| 对话结束 | Agent 轮次结束时 Reflector 触发 | 秒级（复用现有机制） |
| 手动触发 | 用户执行 `/wiki compile` 命令 | 按需 |

### 编译流程

```python
class WikiCompiler:
    """将原始素材增量编译进 wiki 结构"""

    async def compile(self, source: WikiSource) -> CompileResult:
        # 1. 读取当前 index.md，了解已有页面结构
        # 2. 让 LLM 判断：更新已有页面 or 创建新页面
        # 3. LLM 生成/更新 Markdown 内容
        # 4. 写入文件，更新 index.md
        # 5. 返回变更摘要
```

LLM 编译指令（system prompt 片段）：
- 你是知识编辑者，负责将新素材整合进现有 wiki
- 读取 index.md 了解当前结构
- 决定：更新已有页面（追加/修改）还是创建新页面
- 保持页面间交叉引用（`[[page-name]]` 语法）
- 每个页面聚焦一个主题，过长时拆分
- 更新 index.md 反映最新结构

### 页面格式规范

```markdown
# 页面标题

> 最后更新: 2026-05-25 | 来源: 周例会纪要、客户邮件

## 核心要点
- ...

## 详细内容
...

## 相关页面
- [[other-page]]

## 来源追溯
- 2026-05-25 周例会 → 新增"泊位调整"段落
- 2026-05-20 客户邮件 → 更新联系人信息
```

## 路由判断层

### 规则引擎（优先）

```python
class WikiRagRouter:
    def route(self, file: UploadedFile, user_override: str | None = None) -> str:
        if user_override:
            return user_override  # "wiki" | "rag"

        # 硬规则
        if file.page_count and file.page_count > 15:
            return "rag"
        if file.text_size > 50_000:  # > 50KB 文本
            return "rag"
        if self._is_academic_paper(file):
            return "rag"
        if self._is_meeting_minutes(file):
            return "wiki"
        if file.text_size < 10_000 and file.format in ("md", "txt"):
            return "wiki"

        # 模糊地带 → LLM 判断
        return "llm_decide"
```

### LLM 兜底判断

当规则无法确定时，提取文件前 500 字 + 元数据，让 LLM 判断：
- 这份内容适合编译成结构化 wiki 页面，还是作为检索源保留原文？
- 判断依据：内容是否需要综合归纳、是否会被反复引用更新、是否需要精确原文引用

## Agent 使用 Wiki

### System Prompt 注入

每次对话开始时，将 `wiki/index.md` 内容注入 system prompt：

```
## 你的知识 Wiki
以下是你维护的结构化知识库索引，需要详细信息时使用 read_wiki 工具：

{index.md 内容}
```

### read_wiki 工具

```python
@tool(name="read_wiki")
async def read_wiki(page_name: str) -> str:
    """读取 wiki 中指定页面的完整内容"""
    path = WIKI_DIR / f"{page_name}.md"
    if not path.exists():
        return f"页面 '{page_name}' 不存在。可用页面见 index。"
    return path.read_text()
```

Agent 在对话中根据需要主动调用此工具，获取具体知识页面内容。

## API 设计

### 现有接口扩展

```
POST /api/knowledge/upload
  新增 query param: ?target=auto|wiki|rag  (默认 auto)
  响应新增字段: { "routed_to": "wiki" | "rag", "route_reason": "..." }
```

### 新增 Wiki 接口

```
GET  /api/wiki/                    ← 获取 index（页面列表）
GET  /api/wiki/{page_name}         ← 读取指定页面
POST /api/wiki/compile             ← 手动触发编译
PUT  /api/wiki/{page_name}         ← 手动编辑页面
DELETE /api/wiki/{page_name}       ← 删除页面
GET  /api/wiki/history/{page_name} ← 页面变更历史
```

## 与现有模块的关系

| 模块 | 关系 |
|------|------|
| Knowledge（RAG） | 并行存在，共享上传入口，各自独立存储和检索 |
| Memory | 独立模块，agent 记忆/技能仍由 Memory 管理，不进 wiki |
| Skill Router | wiki 内容可作为 skill 的知识源，但 wiki 本身不是 skill |
| Meeting ASR | 会议结束事件触发 wiki 编译，ASR 产出是 wiki 的输入源之一 |

## 前端交互

### 知识管理页面扩展

- 现有「知识库」tab 保留（RAG 文档列表）
- 新增「Wiki」tab：
  - 左侧：页面目录树（基于 index.md 生成）
  - 右侧：页面内容展示（Markdown 渲染）
  - 支持手动编辑和保存
  - 显示来源追溯和更新时间

### 上传交互

- 上传后显示路由结果："已自动归入 Wiki" / "已自动归入知识库"
- 提供切换按钮，用户可覆盖路由决策

## 实现边界

### v4.3.2 范围内

- Wiki 编译管线（WikiCompiler）
- 路由判断层（WikiRagRouter）
- read_wiki 工具注册
- Wiki CRUD API
- 前端 Wiki tab 基础展示
- 会议结束 → wiki 编译事件集成

### 后续迭代

- Wiki 页面间自动链接分析
- Wiki 内容过期检测和提醒
- 多用户协作编辑冲突处理
- Wiki 搜索（当页面数量增长后）
- Wiki 导出（PDF/Notion/Confluence）
