# Changelog

## v2.3.0 (2026-05-09)

### 新增

- 🎨 **前端重设计** — 欢迎页快捷入口卡片 + 消息卡片式布局 + 命令彩色横幅
- 📝 **Markdown 渲染** — marked.js + highlight.js 语法高亮（13 种语言按需加载）
- 📋 **代码块复制按钮** — 一键复制代码，带 ✓ 反馈动画
- 🔍 **侧栏瘦身** — 模型选择从大面板改为单行 Popover，会话列表释放全部空间
- 🔎 **会话搜索/分组** — 实时搜索 + 今天/昨天/更早分组
- ⌨️ **键盘快捷键** — Ctrl+Enter 发送 / Ctrl+/ 命令面板 / Ctrl+L 新会话
- 📏 **输入框自适应高度** — 内容超过 1 行自动增高（最多 6 行）
- 🖼️ **自定义 Logo** — 支持 PNG favicon + 侧栏/Header 图片 Logo
- ⚡ **highlight.js 按需加载** — ChatView.js 从 1002KB 缩减到 132KB（-87%）
- 🔧 **PLAN/BRAINSTORM 提示词精简** — prompt 从 103 字符减到 49 字符
- ⏱️ **工具调用耗时显示** — 前端工具卡片展示每个工具执行时长
- 🏠 **默认 SOUL.md 更新** — 反映 TARS 工程助手定位 + 实际工具列表
- 🔄 **ToolDispatcher 降级增强** — 空响应时自动去工具重试 + 追加总结请求

---

## v2.2.0 (2026-05-09)

### 新增

- 🧠 **记忆认知架构重做** — Scene Analyzer + Semantic Memory + MemoryRouter + SkillRouter
- 🗂️ **Semantic Memory（实体图）** — 确定性哈希 ID + aliases FTS5 合并 + 属性历史
- 🔀 **MemoryRouter** — 实体路/时间线路/向量路/关键词路四路融合 + HybridSearch 兜底降级
- ⚡ **SkillRouter** — 基于意图+实体+关键词的动态技能激活，替代永久注入
- 🪝 **Skill Hooks** — on_activate/pre_llm/post_llm 三阶段钩子 + SkillContext
- 🔍 **Scene Analyzer** — 同步意图识别 + fast_path 跳过 + 语义缓存
- 📝 **Reflector 重做** — upsert_entity/upsert_relation/log_episode 分流写入 + project_context 自动派生
- 🆘 **紧急写入通道** — `archival_insert` 工具，用户说"记住X"时同步写入
- 🗑️ **遗忘机制** — 重要性自然衰减 + 过期自动清理 + Reflector forget
- 🏗️ **Working Context** — 会话级场景画像，72h 自动清理

---

## v2.1.0 (2026-05-06)

### 新增

- 🚀 **Python 沙箱执行** (`python_exec`) — Agent 可写 Python 代码并执行，支持 pandas/numpy/Pillow 等
- ⚡ **斜杠命令系统** — `/plan` `/yolo` `/brainstorm` `/subagent` `/skill` `/clear` `/help`，前端 `/` 按钮下拉菜单
- 🧠 **记忆系统强化** — 核心记忆自动去重 + 行数上限；CJK 中文 LIKE 降级搜索；遗忘机制
- 🏪 **SkillHub 改进** — 本地技能目录 (`/catalog`)；安装状态标注；安装后用法说明；兼容性校验
- 🔗 **WebSocket 持久连接** — wsStore 全局管理，切换页面不断连
- ⌨️ **输入优化** — Enter 键换行，仅鼠标点击提交

---

## v2.0.0 (2026-05-06)

### 新增

- 工具系统全面重构（ToolDispatcher + Function Calling）
- 技能插件系统（PluginSkill + PromptSkill + skill.yaml）
- SkillHub 市场（GitHub Releases）
- 文件上传与多模态理解
- 前端 Tab 布局 + 工具调用可视化
- 多会话独立历史 + 新建/切换/删除

---

## v1.0.0 (2026-05-05)

### 新增

- 基础聊天功能
- 多用户权限系统（admin/user/guest）
- 子代理系统（Code/Writing/Data/Research/Plan）
- 人格参数系统（10 项可调参数）
- 定时任务
- 自进化系统

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
