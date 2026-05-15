# Changelog

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
