# TARS 项目路线图

## 功能模块思维导图

```mermaid
mindmap
  root((TARS Agent))
    核心架构
      五层架构
        Channels 通道层
        Gateway 网关层
        Agent 智能体层
        Model 模型层
        Execution 执行层
      工作区文件系统
        SOUL.md
        AGENTS.md
        MEMORY.md
        USER.md
    前端
      聊天界面
      人格编辑
      记忆管理
      技能市场
      工作看板
      系统设置
    后端
      FastAPI 服务
      WebSocket 通信
      SQLite 数据库
      FTS5 全文索引
    工具系统
      terminal 命令执行
      file 文件操作
      web 网络搜索
      memory 记忆管理
    技能生态
      技能加载
      技能激活
      技能市场
    部署
      Docker
      桌面端 Tauri
```

---

## 实施甘特图

```mermaid
gantt
    title TARS 项目实施计划
    dateFormat  YYYY-MM-DD
    section 骨架
    项目初始化        :done, p1, 2026-05-05, 1d
    FastAPI 服务      :done, p1, after p1, 2d
    React 前端        :done, p1, after p1, 2d
    WebSocket 连接    :done, p1, after p1, 1d

    section 对话
    Agent Loop        :done, p2, after p1, 3d
    LLM Provider      :done, p2, after p2, 2d
    流式输出          :done, p2, after p2, 2d
    会话管理          :done, p2, after p2, 2d

    section Gateway
    身份核验          :done, p3, after p2, 1d
    Session 路由      :done, p3, after p3, 1d
    速率限制          :done, p3, after p3, 1d
    安全策略          :done, p3, after p3, 2d

    section SOUL
    工作区文件解析    :done, p4, after p3, 2d
    人格参数调节      :done, p4, after p4, 2d
    System Prompt     :done, p4, after p4, 1d

    section 记忆
    双层存储          :done, p5, after p4, 2d
    自动提取          :done, p5, after p5, 2d
    FTS5 检索        :done, p5, after p5, 1d

    section 工具
    工具注册表        :done, p6, after p5, 1d
    terminal 工具     :done, p6, after p6, 1d
    file 工具         :done, p6, after p6, 1d
    web 工具          :done, p6, after p6, 1d
    memory 工具       :done, p6, after p6, 1d

    section 技能
    技能加载          :done, p7, after p6, 2d
    技能激活/停用     :done, p7, after p7, 1d
    技能市场          :done, p7, after p7, 2d

    section 完善
    PWA 支持          :done, p8, after p7, 1d
    工作看板          :done, p8, after p8, 2d
    系统设置          :done, p8, after p8, 1d
    深色模式          :done, p8, after p8, 1d
    响应式设计        :done, p8, after p8, 1d

    section 桌面化
    Tauri 包装        :p9, after p8, 2d
    系统托盘          :p9, after p9, 1d
    文件关联          :p9, after p9, 1d
```

---

## 里程碑清单

| 里程碑 | 目标 | 交付物 | 预计完成时间 |
|--------|------|--------|-------------|
| M1: 项目启动 | 基础项目结构、依赖配置 | 代码仓库、pyproject.toml、package.json | 2026-05-06 |
| M2: 可对话 | 完成基础聊天功能 | Web 界面、基本对话、流式输出 | 2026-05-15 |
| M3: 安全通道 | Gateway 层功能完整 | 身份核验、限流、安全策略 | 2026-05-20 |
| M4: 可调人格 | 工作区系统完整 | SOUL/AGENTS/MEMORY/USER 管理 | 2026-05-27 |
| M5: 有记忆 | 记忆系统完整 | 双层存储、自动提取、FTS5 检索 | 2026-06-03 |
| M6: 能执行 | 工具系统完整 | 4 个核心工具、安全隔离 | 2026-06-15 |
| M7: 可扩展 | 技能系统完整 | 技能加载、技能市场 | 2026-06-22 |
| M8: Web 产品 | 前端功能完整 | PWA、看板、设置、深色模式 | 2026-07-01 |
| M9: 桌面端 | 桌面应用完成 | Tauri 包装、系统集成 | 2026-07-10 |

---

## 分阶段实施计划详细

### Phase 1: 骨架 (✅ 完成)
**目标:** 项目初始化、基础架构搭建
**验收日期:** 2026-05-05
- ✅ 后端: FastAPI 项目、目录结构
- ✅ Channels 层抽象: Channel、ChannelMessage
- ✅ WebSocket 连接管理: ConnectionManager、心跳机制
- ✅ 前端: React + Vite + TypeScript + Tailwind + Zustand
- ✅ 通信: WebSocket 基础连接、Welcome 事件、Ping/Pong

### Phase 2: 对话 (✅ 完成)
**目标:** 基础对话功能
**验收日期:** 2026-05-05
- ✅ Agent Loop 实现
- ✅ LLM Provider 抽象
- ✅ 流式输出支持
- ✅ 会话管理（SQLite）
- ✅ 集成: Channels ↔ Agent ↔ Model
- ✅ 前端: 聊天界面、流式显示

### Phase 3: Gateway (✅ 完成)
**目标:** 安全可靠的消息通道
**验收日期:** 2026-05-05
- ✅ AuthManager: API Key 身份验证
- ✅ RateLimiter: Token Bucket 速率限制
- ✅ SecurityPolicy: 危险命令检测、路径白名单、内容过滤
- ✅ Gateway 主类: 整合所有网关功能

### Phase 4: SOUL (✅ 完成)
**目标:** 可配置的 Agent 人格
**验收日期:** 2026-05-05
- ✅ Soul 人格定义系统: SoulIdentity, SoulParameters, Soul
- ✅ SOUL.md 解析器
- ✅ USER.md 用户画像系统
- ✅ MEMORY.md 长期记忆系统
- ✅ WorkspaceManager: 工作区管理器
- ✅ System Prompt 动态构建

### Phase 5: 记忆 (✅ 完成)
**目标:** 持续学习和记忆
**验收日期:** 2026-05-05
- ✅ Database 扩展: memories 表 + memories_fts FTS5 索引
- ✅ Memory 数据类: id, content, category, importance, timestamp
- ✅ MemoryManager: 记忆管理器
- ✅ MemoryExtractor: 记忆提取器（正则匹配）
- ✅ FTS5 全文搜索: search_memories()
- ✅ 记忆自动提取: extract_and_save()
- ✅ 记忆上下文注入: get_context_for_query()

### Phase 6: 工具 (✅ 完成)
**目标:** 强大的执行能力
**验收日期:** 2026-05-05
- ✅ BaseTool: 工具抽象基类
- ✅ ToolRegistry: 工具注册表
- ✅ TerminalTool: 终端命令执行（安全检查）
- ✅ FileTool: 文件操作（read/write/list/delete/exists）
- ✅ WebTool: 网络搜索和网页获取
- ✅ MemoryTool: 记忆管理（add/search/list/delete）
- ✅ 安全隔离: 所有工具都经过 SecurityPolicy 检查

### Phase 7: 技能 (✅ 完成)
**目标:** 可扩展的技能生态
**验收日期:** 2026-05-05
- ✅ SKILL.md 格式解析器 (SkillParser)
- ✅ SkillLoader: 技能加载器
- ✅ 技能激活/停用功能
- ✅ 技能市场前端 UI
- ✅ 技能管理 API (GET/POST /api/skills)
- ✅ 5 个默认技能（天气查询/计算器/待办清单/故事生成器/代码助手）

### Phase 8: 完善 (✅ 完成)
**目标:** 完整的 Web 产品
- ✅ PWA 支持 (vite-plugin-pwa, manifest.json, 离线缓存)
- ✅ 工作看板页面 (UI 已完成)
- ✅ 系统设置页面
- ✅ 深色/浅色模式切换
- ✅ 响应式设计

### Phase 9: 桌面化
**目标:** 桌面客户端
- Tauri 包装
- 系统托盘
- 文件关联

---

*文档版本: v1.8*
*创建日期: 2026-05-05*
