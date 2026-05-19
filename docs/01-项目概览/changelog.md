# Changelog

## v4.1.4 "Memory Entity Tree" (2026-05-19)

记忆管理新增实体树可视化（Phase 1–3）。

### 记忆实体树
- ✅ **`GET /api/memory/tree`** — 实体视图 / 压缩谱系视图（`view=entity|provenance`）
- ✅ **`GET /api/memory/tree/relations`** — 实体关系边
- ✅ **`GET /api/memory/tree/search`** — 树内搜索与路径展开
- ✅ **实体 Tab** — 左树右详情；搜索、Admin 用户联动、跳转长期记忆
- ✅ **谱系视图** — 压缩记忆与 `compressed_from` 来源/已归档
- ✅ **关系迷你图** — 选中实体 SVG 邻接图，点击跳转对应实体
- ✅ **大树优化** — 节点 >120 默认仅展开顶层

---

## v4.1.3 "Chat Polish & Remember" (2026-05-19)

聊天体验精简与手动「记住要点」能力。

### 聊天 UX
- ✅ **紧凑顶栏** — ChatView 单行状态栏；移除 Plan Mode / Brainstorm 按钮
- ✅ **DesktopShell 精简** — 移除 Graphite Amber 徽章、页头模型入口；通知铃移至左侧栏
- ✅ **Ctrl/⌘+Enter 发送** — Enter 仅换行
- ✅ **回复复制** — 助手消息一键复制完整原文（含工具输出）
- ✅ **RightPanel 折叠标签** — 中英文均竖排显示，避免与图标重叠

### 记住要点
- ✅ **`POST /api/memory/extract-from-turn`** — 从一轮对话提取可保存记忆草稿
- ✅ **`POST /api/memory/save-from-turn`** — 用户确认后写入 archival 记忆
- ✅ **RememberMemoryDialog** — 聊天内 🧠「记住要点」预览、编辑、分类保存
- ✅ **LLM 提取 fallback** — 解析为空时回退 RegexExtractor

---

## v4.1.2 "Skill Ops & Platform UI" (2026-05-19)

v4.1.1 后续：Curator 运维、Admin 平台工具、技能生态扩展。

### Curator 运维
- ✅ **`GET /api/skills/pending-archive`** — 列出待归档技能
- ✅ **启动自动归档** — `check_auto_archive` 在 startup 按 `auto_archive_days` 执行
- ✅ **待归档 UI** — ToolsView 技能 Tab 展示并一键归档

### Admin 平台工具
- ✅ **Provider 用量表** — Admin → 平台工具
- ✅ **记忆导出** — 一键下载租户记忆 JSON

### 技能生态
- ✅ **内置技能扩至 22 个** — 新增邮件/SQL/API/文档等 12 个 prompt 技能
- ✅ **Scene Analyzer → SkillRouter** — WC `current_intent` 参与路由
- ✅ **SkillHub 安装 scope** — Admin 可选 tenant / global

---

## v4.1.1 "Experience Layer" (2026-05-19)

> 完整发布说明见 [v4.1.1-release-notes.md](./v4.1.1-release-notes.md)

### 体验层
- ✅ SkillHub 安装向导（成功页 / 依赖跳过 / Try Skill）
- ✅ 聊天页「已激活技能」条（`skills_active` WebSocket）
- ✅ 知识引用 `[ref:doc_id|标题]` + 侧边预览面板
- ✅ 设置页 v4.1.1 / v4.1.0 / v4.0.0 Changelog
- ✅ 切页面会话不断（全局 chatRealtime store + KeepAlive）

---

## v4.1.0 "Skill Ecosystem" (2026-05-19)

技能生态正式版：三源 SkillHub、SkillRouter 激活、多租户隔离、知识引用溯源。

### SkillHub & 技能激活（Phase 1–2）

- ✅ **skills.sh + GitHub 三源搜索** — bundled / skills.sh / GitHub 合并目录
- ✅ **DependencyChecker** — 安装前 bins/packages 依赖检查，`needs_setup` 响应
- ✅ **SkillRouter** — 信号提取 + 内容匹配按需注入，替代永久 Prompt 注入
- ✅ **斜杠命令** — `/skill list`、`/skill find`、`/skill off`
- ✅ **Try Skill** — ToolsView 一键试用 + ChatView `?prompt=` 预填
- ✅ **`POST /api/skills/reload`** — 真正 reload SkillLoader

### 多租户技能隔离（Phase 3）

- ✅ **`skills/_global/` + `skills/tenants/{id}/`** — 目录布局 + 启动自动迁移
- ✅ **tenant-scoped 安装** — 默认 `scope=tenant`，admin 可装 global
- ✅ **SkillRegistry.list_for_tenant** — Agent/API 按 tenant 过滤可见技能

### 模块流水线（Phase 4）

- ✅ **知识引用溯源** — `[ref:doc_id]` 标注 + Chat 可点击引用卡片
- ✅ **会议入库验收** — approve-to-knowledge 后 search_knowledge 可检索
- ✅ **BI 查询审计** — `bi_query` action + sql_hash/row_count
- ✅ **审计台分组** — action_group 筛选（skill/tool/bi/auth/memory）

### 平台增强（Phase 5）

- ✅ **Provider Fallback** — `config/providers.yaml` chain + `chat_with_fallback()`
- ✅ **model_fallback 审计** + **provider_usage 表** + `GET /api/providers/usage`
- ✅ **记忆导出** — `GET /api/memory/export?user_id=`

### 测试

- 新增 test_skillhub_v41、test_tenant_skills、test_knowledge_citations、test_provider_fallback 等

---

## v4.0.5 "Skill Ecosystem Preview" (2026-05-19)

技能生态预览版：SkillHub 本地可安装、知识库与 Agent 联动、Admin 管理台完善。

> 完整发布说明见 [v4.0.5-release-notes.md](./v4.0.5-release-notes.md)

### SkillHub 技能生态

- ✅ **LocalSkillCatalog** — bundled 本地技能目录，扫描 `data/skillhub/skills/` + `skillhub_catalog.json`
- ✅ **10 个可安装技能** — PDF、GitHub、Excel、浏览器自动化、技能发现、摘要、天气、会议纪要、BI 等
- ✅ **SKILL.md 安装支持** — 兼容 Agent Skills 规范，安装后自动注册并启用
- ✅ **上下文技能注入** — Agent 按用户消息关键词匹配并注入 Prompt 技能全文
- ✅ **前端精选筛选** — featured 标签、安装用法与 example_prompt 展示

### 知识库

- ✅ **统一检索层** — `knowledge/access.py` 供 API、工具、Agent 共用
- ✅ **sqlite_store** — 知识库元数据 SQLite 存储
- ✅ **Agent 主动检索** — 每轮对话前自动 search_knowledge，WebSocket 推送进度
- ✅ **会议入库** — `POST /api/meeting/{id}/approve-to-knowledge` 转写入库

### 会议助手

- ✅ **摘要 API** — summarize / update_summary / 自定义 Prompt 模板
- ✅ **Stale 恢复** — 超时转写任务自动标记失败
- ✅ **前端 meetingSummary** — 结构化摘要 JSON 解析

### Admin 管理台

- ✅ **AdminView 壳** — 用户 / 角色 / 审计 Tab 导航
- ✅ **UserEditDrawer** — 用户编辑（含密码修改）
- ✅ **reset_admin.py** — 管理员账号重置脚本
- ✅ **审计扩展** — 用户/会话/配置/技能事件日志

### 记忆与其他

- ✅ **Memory API** — pin / promote / scope / merge / compress
- ✅ **SearXNG 部署** — `deploy/searxng/` Docker 私有搜索
- ✅ **chatMarkdown** — 聊天气泡 Markdown 渲染增强
- ✅ **roleDisplay** — 角色模板显示工具

### 测试

- 新增 test_skillhub_local、test_knowledge_search_tool、test_meeting_knowledge、test_admin_memory_api 等

### 规划文档（v4.1.0 前瞻，未实现）

- 📋 v4.1.0 建设方案 / 技术方案 / 执行计划

---

## v4.0.0 "Hardened Base" (2026-05-17)

多用户内网部署底座加固：安全、性能、Provider 插件化、模块化启动。

### Phase 1: Security Hardening（安全加固）

- ✅ **敏感信息脱敏引擎** — 正则模式库检测 API Key / 手机号 / 邮箱 / 银行卡 / 私钥 / 密码字段，支持 partial mask 和 full redact 两种模式
- ✅ **提示词注入防护** — 5 类攻击模式检测（delimiter injection / role override / jailbreak / context boundary / hidden command），severity 分级，教育讨论不误杀
- ✅ **审计日志系统** — 全量记录工具调用、权限拒绝、记忆操作、模型调用，SQLite 持久化 + REST 查询 API（admin 鉴权）
- ✅ **记忆权限管理** — private/shared 双作用域，跨租户隔离，admin 可管理所有用户记忆，检索自动包含 shared 记忆
- ✅ **角色工具权限** — `config/tool_permissions.yaml` 配置 admin/user/guest 工具白名单，dispatcher 层拦截 + 审计记录
- ✅ **Admin 记忆管理 API** — 用户记忆统计、详情查看、清空私有记忆、创建/删除共享记忆

### Phase 2: Performance（性能优化）

- ✅ **延迟导入** — `lazy.py` 工具类 + embedding 模型首次使用时加载，冷启动加速
- ✅ **Skills Manifest Cache** — 技能目录 mtime 快照缓存，二次启动跳过重扫（4.3x 加速）
- ✅ **LLM 连接复用池** — 单 httpx.AsyncClient 共享，支持环境变量覆盖超时，shutdown 时正确关闭
- ✅ **Prompt Cache** — 静态部分（persona + tools）TTL 缓存，动态部分（memory_context）每次重建，线程安全 + LRU eviction
- ✅ **并发限流** — asyncio.Semaphore + per-user 计数器，YAML 配置 max_concurrent / per_user_max / queue_timeout，超限返回友好提示

### Phase 3: Provider Plugin Architecture（Provider 插件化）

- ✅ **ProviderBase ABC** — 统一抽象接口（chat / list_models / test_connection），ChatResponse / ModelInfo dataclass
- ✅ **ProviderRegistry** — 自动注册 builtin，支持外部 register，get_instance 缓存
- ✅ **OpenAI Compatible Provider** — 合并 custom + openrouter，quirks 适配（tool_call_nested 等）
- ✅ **Ollama Plugin 迁移** — 旧文件改为 redirect，消除双份实现
- ✅ **配置化** — `config/providers.yaml` 声明式配置，`${ENV_VAR}` 展开，`scripts/migrate_providers.py` 自动迁移
- ✅ **热切换** — agent.switch_model 支持 provider_name 参数，运行时切换无需重启
- ✅ **API 端点** — `GET /api/providers` 列表 + `POST /api/providers/{name}/test` 连接测试

### Phase 4: Platform Polish（平台收尾）

- ✅ **模块化启动** — `config/modules.yaml` 控制可选模块（bi / meeting / knowledge / skillhub），未启用模块不注册路由
- ✅ **Skill Curator** — 技能使用统计（调用次数 / 最后使用时间），archive/activate 状态管理，SkillRouter 跳过已归档技能
- ✅ **API 端点** — `GET /api/modules` 模块状态 + `GET /api/skills/stats` 技能统计 + `PUT /api/skills/{id}/archive`

### 测试

- 157 个单元/集成测试全部通过
- 覆盖：脱敏引擎、审计日志、注入防护、记忆权限、连接池、Prompt Cache、限流器、Provider 基类/注册、模块加载、技能统计、工具调度

### 配置文件新增

- `backend/config/providers.yaml` — LLM Provider 配置
- `backend/config/modules.yaml` — 可选模块启用/禁用
- `backend/config/concurrency.yaml` — 并发限流参数
- `backend/config/tool_permissions.yaml` — 角色工具权限

---

## v3.9.1 (2026-05-16)

### 视觉统一收口（Graphite Amber）

- ✅ **Graphite Amber 视觉体系** — 全站深色暖系改造，琥珀（amber）替换蓝色（blue）主色调，背景 #0c0b09 / #14110f，琥珀主色 amber-500
- ✅ **DesktopShell 桌面态可折叠窄栏** — 右栏支持展开/折叠态，localStorage 持久化，48px 窄栏 + 展开恢复把手，CSS 变量 `--inspector-width` 控制宽度
- ✅ **通用弹层壳 AppSurfaceDialog / AppSurfaceDrawer** — 统一视觉边界，居中弹窗 + 侧边抽屉，覆盖 Tools/Memory/Knowledge/BI/Settings 核心弹层
- ✅ **会议助手视觉统一** — MeetingSettings / RecordingPanel / TranscriptionList / TranscriptionDetail / SchemaAnnotator 全链路深色化
- ✅ **知识库视觉统一** — KnowledgeManager / DocumentUploader 深色化改造
- ✅ **记忆助手视觉统一** — MemoryCard / RecentMemoryTab / LongtermMemoryTab / AllMemoryTab 全链路深色化
- ✅ **BI 工作台视觉统一** — DataSourceSettings / BiAnalyticsView 深色化改造
- ✅ **Chat 聊天气泡统一** — 工具调用卡片 / 步骤面板 / 代码块 / 表格 / 内联代码全部改琥珀色系
- ✅ **ChartRenderer 按需加载** — defineAsyncComponent 动态导入，不影响首屏体积
- ✅ **ESC 键盘关闭** — AppSurfaceDialog / AppSurfaceDrawer 支持 ESC 键关闭
- ✅ **侧栏快捷图标** — 折叠态新增设置 / 模型 / 语言切换快捷入口
- ✅ **Models 页面清理** — 删除多余的语言切换按钮和返回聊天按钮
- ✅ **滚动修复** — MemoryView / MeetingView left-panel overflow-y: auto 修复滚动条不可见问题
- ✅ **19 个前端单元测试全通过**

### 设计文档新增

- ✅ `docs/superpowers/plans/2026-05-16-workspace-shell-dialog-unification.md` — 桌面折叠 + 弹层统一实施计划
- ✅ `docs/superpowers/specs/2026-05-16-workspace-shell-dialog-unification-design.md` — 视觉规范文档

---



### 会议助手

- ✅ 实时录音转写（边录边转）：WebSocket 流式传输 + ProcessPoolExecutor 非阻塞
- ✅ 3 套专业摘要模板：通用商务型（默认）、执行摘要型、项目进度型
- ✅ 自定义提示词编辑 + 保存
- ✅ 会议模块独立模型配置（不影响主 Agent）
- ✅ 录音不足 5 秒自动截断提示
- ✅ 会议纪要编辑确认入库知识库（摘要索引 + 原文追溯）
- ✅ 入库文档名使用摘要主题 + 日期

### 知识库增强

- ✅ Agent 主动调用 knowledge_search（system prompt 规则引导）
- ✅ knowledge_search 未指定 collection 时自动搜索所有 collections
- ✅ 会议纪要固定 collection（meeting_notes_kb）

### 稳定性修复

- ✅ 调度器无限触发 bug（next_run 在 create_task 前更新）
- ✅ migration worker 死锁（禁用共享 SQLite 连接的后台线程）
- ✅ 模型切换后 meeting_tool.provider 同步更新
- ✅ Vite 代理启用 /api WebSocket 转发
- ✅ 前端 i18n 补充会议助手翻译 + 类型修复
- ✅ transcriptions 表自动迁移 approved_at/knowledge_doc_id 列

### 环境变更

- 后端统一使用 `.venv` 虚拟环境
- 删除旧 `venv` 目录
- 启动命令：`.venv/bin/python -m uvicorn tars.main:app --host 0.0.0.0 --port 8000`

---

## v2.7.0 (2026-05-16)

### 核心架构升级

- ✅ **多租户支持（TenantContext）**：请求级租户隔离，LRU 缓存，所有数据表加 tenant_id
- ✅ **REST 同步调用接口**：`POST /api/invoke`，支持同步 + SSE 流式
- ✅ **Skill Pipeline 编排**：声明式 YAML pipeline，skill 间变量传递
- ✅ **结构化输出**：ToolDispatcher 支持 response_format / JSON schema 约束

### 模型配置重构

- ✅ Provider 简化为 Ollama + OpenAI 兼容两类
- ✅ 新增 Endpoint 概念，支持端点 + 模型列表管理
- ✅ 侧边栏无 tab 分组，统一 `/api/models/switch` 热切换

### BI Analytics Skill

- ✅ 多数据库支持（MySQL/PostgreSQL/Oracle/SQL Server/ClickHouse）
- ✅ SQL Agent + 自我修正（最多 3 轮 LLM 重试）
- ✅ SQL 安全层：只允许 SELECT/WITH，LIMIT 1000，30s 超时
- ✅ Schema 自动抓取 + LLM 推断 + 用户标注
- ✅ ECharts 图表生成 + 前端渲染组件

### 向量搜索与知识库升级

- ✅ Reranker 精排集成到搜索管线
- ✅ PDF/DOCX 文档解析（pymupdf + python-docx）
- ✅ 知识库查询扩展（同义词变体）
- ✅ 批量索引 API
- ✅ Embedding 模型运行时切换
- ✅ Agent 自动注入知识库上下文（top-3 相关片段）
- ✅ chunk_size 300 + overlap 100 + 文件名前缀

### 通知系统修复

- ✅ WebSocket 投递失败时自动 fallback 到 broadcast
- ✅ cron reminder 按 session_id 定向投递
- ✅ API 序列化 None 保护

### 修复

- ✅ sql_agent ChannelMessage → ChatMessage
- ✅ ChromaDB 维度冲突（384 vs 512）
- ✅ 知识库文档删除清理 Chroma chunks

### 依赖变更

- 新增：chromadb, pymupdf, python-docx, sqlalchemy, pymysql, psycopg2-binary, sqlparse
- 后端启动方式：`.venv/bin/python -m uvicorn tars.main:app --host 0.0.0.0 --port 8000`

---

## v2.6.0 (2026-05-11)

### 新增

- ✅ 技能融合设计（Agent Skills 规范对齐）
- ✅ SKILL.md 解析器 + skills_v3 表
- ✅ PDCA.yaml 解析器 + 变量引擎
- ✅ deploy / run_tests / release_notes 三个技能迁移
- ✅ 权限引擎 + 运行时检查
- ✅ `/skill permissions/revoke` 命令
- ✅ 危险命令组合警告
- ✅ 渐进披露触发机制

### 设计决策

- 采用 Anthropic Agent Skills 规范，技能定义从 YAML 改为 SKILL.md
- LLM 读 description 决定激活，不再依赖关键词匹配
- PDCA 从全局强加变为技能可选装备
- 权限系统支持按技能细粒度授权

---

## v2.4.0 (2026-05-09)

### 新增

- ✅ 任务自动化完整实现
- ✅ TaskDetector 触发检测
- ✅ TaskWorkspace 路径解析 + SQLite 持久化
- ✅ StepVerifier 六种验证类型
- ✅ ActPolicy 失败决策（重试→跳过→中止）
- ✅ ArtifactsCollector 产出收集
- ✅ TaskPanel 抽屉组件（ChatView 内嵌）
- ✅ WebSocket 任务状态实时推送
- ✅ 崩溃恢复机制

### 设计决策

- 触发条件：显式 `/plan` 命令或消息包含关键词（部署/构建/发布/测试）
- 消息长度需 > 50 字符过滤短消息
- TaskPanel 作为 ChatView 右侧抽屉，不新增独立路由
- 任务产出展示 artifacts + output_summary

---

## v0.1.0 (2026-05-05)

### 新增

- ✅ 完整的五层架构设计
- ✅ 文档体系建设计划
- ✅ 系统全景图
- ✅ 分层详细设计图
- ✅ 数据流图
- ✅ WebSocket 通信协议
- ✅ 组件关系图
- ✅ 数据库 ER 图
- ✅ 项目路线图（含甘特图）
- ✅ 项目概览文档

### 设计决策

- 采用 OpenClaw 五层架构 + Hermes 工具注册表
- 工作区精简为 4 个核心文件（SOUL/AGENTS/MEMORY/USER）
- 短期记忆使用 SQLite FTS5 而非每日 .md 文件
- Gateway 层与 Agent 层同进程部署，适合浏览器端优先策略
- 前端状态管理采用 Zustand，轻量且 TS 友好

---

*文档版本: v1.0*  
*创建日期: 2026-05-05*
