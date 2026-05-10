# Changelog

## v2.5.0 (2026-05-09)

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
