# 组件关系图

## 后端组件依赖关系

```mermaid
graph TB
    subgraph Channels 通道层
        WebChannel[web.py<br/>WebSocket Channel]
        TelegramChannel[telegram.py<br/>Telegram Bot]
        FeishuChannel[feishu.py<br/>Feishu Bot]
        ChannelBase[base.py<br/>Channel ABC]
    end
    
    subgraph Gateway 网关层
        Auth[auth.py<br/>身份验证]
        RateLimit[rate_limit.py<br/>速率限制]
        Router[router.py<br/>Session 路由]
        Security[security.py<br/>安全策略]
    end
    
    subgraph Agent 智能体层
        Core[core.py<br/>Agent Loop]
        Workspace[workspace.py<br/>工作区管理]
        Prompt[prompt.py<br/>System Prompt]
        Session[session.py<br/>会话管理]
    end
    
    subgraph Memory 记忆系统 V3
        Manager[manager.py<br/>记忆管理 Facade]
        CoreMem[core_memory.py<br/>4 块固定区块]
        Archival[archival.py<br/>长期记忆存储]
        Reflector[reflector.py<br/>异步反思器]
        Decay[decay.py<br/>Ebbinghaus 衰减]
        Search[search.py<br/>embedding 检索]
    end
    
    subgraph Model 模型层
        ProviderBase[provider.py<br/>Provider ABC]
        OpenRouterProv[openrouter.py<br/>OpenRouter]
        AnthropicProv[anthropic.py<br/>Anthropic]
        OpenAIProv[openai.py<br/>OpenAI]
        OllamaProv[ollama.py<br/>Ollama]
    end
    
    subgraph Tools 工具层
        Registry[registry.py<br/>ToolRegistry]
        Terminal[terminal.py<br/>terminal 工具]
        FileTool[file.py<br/>file 工具]
        Browser[browser.py<br/>browser 工具]
        WebTool[web.py<br/>web 工具]
        Delegate[delegate.py<br/>delegate 工具]
        CronJob[cronjob.py<br/>cronjob 工具]
        MemoryTool[memory.py<br/>memory 工具]
    end
    
    subgraph Config 配置
        Settings[settings.py<br/>配置管理]
        Defaults[defaults.yaml<br/>默认配置]
    end
    
    %% Main
    Main[main.py<br/>FastAPI 入口] --> Channels
    Main --> Gateway
    Main --> Agent
    
    %% Channels
    WebChannel --> ChannelBase
    TelegramChannel --> ChannelBase
    FeishuChannel --> ChannelBase
    ChannelBase --> Gateway
    
    %% Gateway
    Gateway --> Agent
    Auth --> Settings
    RateLimit --> Settings
    Security --> Settings
    
    %% Agent
    Core --> Workspace
    Core --> Prompt
    Core --> Session
    Core --> Memory
    Core --> Model
    Core --> Tools
    
    %% Memory
    Manager --> CoreMem
    Manager --> Archival
    Manager --> Search
    Archival --> Decay
    Search --> Archival
    Reflector --> Manager
    Core --> Reflector
    
    %% Model
    OpenRouterProv --> ProviderBase
    AnthropicProv --> ProviderBase
    OpenAIProv --> ProviderBase
    OllamaProv --> ProviderBase
    
    %% Tools
    Terminal --> Registry
    FileTool --> Registry
    Browser --> Registry
    WebTool --> Registry
    Delegate --> Registry
    CronJob --> Registry
    MemoryTool --> Registry
    MemoryTool --> Manager
    WebTool --> Reflector
    Registry --> Security
    
    %% Config
    Settings --> Defaults
```

---

## 前端组件依赖关系

```mermaid
graph TB
    subgraph Pages 页面
        ChatPage[ChatPage.tsx<br/>聊天页]
        SoulPage[SoulPage.tsx<br/>人格编辑]
        MemoryPage[MemoryPage.tsx<br/>记忆管理]
        SkillsPage[SkillsPage.tsx<br/>技能市场]
        DashboardPage[DashboardPage.tsx<br/>工作看板]
        SettingsPage[SettingsPage.tsx<br/>系统设置]
    end
    
    subgraph Components 组件
        ChatWindow[ChatWindow.tsx<br/>聊天窗口]
        MessageBubble[MessageBubble.tsx<br/>消息气泡]
        StreamOutput[StreamOutput.tsx<br/>流式输出]
        ToolUseIndicator[ToolUseIndicator.tsx<br/>工具指示器]
        SoulEditor[SoulEditor.tsx<br/>SOUL 编辑器]
        ParamsSlider[ParamsSlider.tsx<br/>参数滑块]
        MemoryList[MemoryList.tsx<br/>记忆列表]
        MemoryEditor[MemoryEditor.tsx<br/>记忆编辑器]
        SkillCard[SkillCard.tsx<br/>技能卡片]
        SkillInstall[SkillInstall.tsx<br/>技能安装]
        TaskBoard[TaskBoard.tsx<br/>任务看板]
        StatsPanel[StatsPanel.tsx<br/>统计面板]
    end
    
    subgraph Stores 状态管理
        ChatStore[chatStore.ts<br/>聊天状态]
        SoulStore[soulStore.ts<br/>人格状态]
        WSStore[wsStore.ts<br/>WebSocket 状态]
    end
    
    subgraph Hooks
        UseWebSocket[useWebSocket.ts<br/>WS Hook]
        UseStream[useStream.ts<br/>流式 Hook]
    end
    
    %% App
    App[App.tsx] --> Pages
    App --> Stores
    
    %% Pages
    ChatPage --> ChatWindow
    ChatPage --> ChatStore
    SoulPage --> SoulEditor
    SoulPage --> ParamsSlider
    SoulPage --> SoulStore
    MemoryPage --> MemoryList
    MemoryPage --> MemoryEditor
    SkillsPage --> SkillCard
    SkillsPage --> SkillInstall
    DashboardPage --> TaskBoard
    DashboardPage --> StatsPanel
    
    %% Components
    ChatWindow --> MessageBubble
    ChatWindow --> StreamOutput
    ChatWindow --> ToolUseIndicator
    ChatWindow --> UseStream
    
    %% Stores
    ChatStore --> UseWebSocket
    WSStore --> UseWebSocket
```

---

## 完整项目文件结构

```mermaid
graph TB
    Root[TARS<br/>项目根目录] --> Frontend[frontend/<br/>前端]
    Root --> Backend[backend/<br/>后端]
    Root --> Docs[docs/<br/>文档]
    Root --> DesignDocs[DESIGN.md<br/>DESIGNV1.md]
    
    Frontend --> FrontendSrc[src/]
    Frontend --> FrontendPublic[public/]
    Frontend --> FrontendPackage[package.json]
    Frontend --> FrontendVite[vite.config.ts]
    
    FrontendSrc --> Components[components/]
    FrontendSrc --> Stores[stores/]
    FrontendSrc --> Hooks[hooks/]
    FrontendSrc --> Pages[pages/]
    FrontendSrc --> AppTs[App.tsx]
    FrontendSrc --> MainTs[main.tsx]
    
    Components --> ChatComp[Chat/]
    Components --> SoulComp[Soul/]
    Components --> MemoryComp[Memory/]
    Components --> SkillsComp[Skills/]
    Components --> DashboardComp[Dashboard/]
    
    Backend --> Tars[tars/<br/>核心包]
    Backend --> Data[data/<br/>数据目录]
    Backend --> PyProject[pyproject.toml]
    Backend --> Requirements[requirements.txt]
    
    Tars --> MainPy[main.py<br/>FastAPI 入口]
    Tars --> ChannelsDir[channels/<br/>通道层]
    Tars --> GatewayDir[gateway/<br/>网关层]
    Tars --> AgentDir[agent/<br/>智能体层]
    Tars --> MemoryDir[memory/<br/>记忆系统 V3<br/>core_memory/archival/<br/>reflector/decay/search/manager]
    Tars --> SkillsDir[skills/<br/>技能系统]
    Tars --> ToolsDir[tools/<br/>工具层]
    Tars --> ModelDir[model/<br/>模型层]
    Tars --> ConfigDir[config/<br/>配置]
    
    Data --> AgentsDir[agents/]
    Data --> SkillsDataDir[skills/]
    Data --> SessionsDir[sessions/]
    Data --> TarsDB[tars.db]
    
    Docs --> Doc01[01-项目概览/]
    Docs --> Doc02[02-技术方案/]
    Docs --> Doc03[03-实施计划/]
    Docs --> Doc04[04-运维文档/]
```

---

## 数据库 ER 图

```mermaid
erDiagram
    SESSIONS ||--o{ MESSAGES : contains
    SESSIONS {
        string id PK
        string agent_id
        string user_id
        string title
        datetime created_at
        datetime updated_at
        string summary
    }

    MESSAGES {
        string id PK
        string session_id FK
        string role
        string content
        datetime timestamp
    }

    CORE_MEMORY_BLOCKS {
        string agent_id PK
        string block_name PK
        string content
        int char_limit
        datetime updated_at
    }

    ARCHIVAL_MEMORY {
        string id PK
        string agent_id
        string content
        blob embedding
        string source
        float importance
        datetime created_at
        datetime last_accessed
        int access_count
    }
```

> 记忆系统 V3 改为 SQLite 持久化：`core_memory_blocks` 存放 4 块固定区块（persona / user_profile / project_context / working_principles）；`archival_memory` 存放长期事实，使用 embedding 检索 + Ebbinghaus 衰减管理生命周期。Reflector 在 Agent 主循环结束后异步触发，自主更新两类记忆。

---

*文档版本: v1.0*  
*创建日期: 2026-05-05*
