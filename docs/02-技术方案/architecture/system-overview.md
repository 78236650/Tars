# TARS 系统全景图

## 五层架构总览

```mermaid
graph TB
    User((用户)) -->|请求| Channels[Layer 1: Channels<br/>通道层]
    
    Channels -->|标准化消息| Gateway[Layer 2: Gateway<br/>网关层]
    
    Gateway -->|路由| Agent[Layer 3: Agent<br/>智能体层]
    
    Agent -->|调用 LLM| Model[Layer 4: Model<br/>模型层]
    
    Agent -->|执行工具| Execution[Layer 5: Execution<br/>执行层]
    
    Execution -->|结果| Agent
    Model -->|响应| Agent
    Agent -->|响应| Gateway
    Gateway -->|响应| Channels
    Channels -->|响应| User
    
    subgraph Channels
        Web[Web<br/>WebSocket]
        Telegram[Telegram<br/>Bot]
        Feishu[飞书/钉钉<br/>Bot]
        Webhook[Webhook<br/>API]
    end
    
    subgraph Gateway
        Auth[身份核验]
        RateLimit[速率限制]
        Router[Session 路由]
        Security[安全策略]
    end
    
    subgraph Agent
        Workspace[工作区<br/>SOUL/AGENTS/MEMORY/USER]
        Loop[Agent Loop<br/>异步流式]
        Memory[记忆系统 V3<br/>Core+Archival+Reflector]
    end
    
    subgraph Model
        OpenRouter[OpenRouter<br/>默认]
        Anthropic[Anthropic]
        OpenAI[OpenAI]
        Ollama[Ollama<br/>本地]
    end
    
    subgraph Execution
        Terminal[terminal<br/>命令执行]
        File[file<br/>文件操作]
        Browser[browser<br/>浏览器]
        Web[web<br/>网络搜索]
        Delegate[delegate<br/>子代理]
        Cronjob[cronjob<br/>定时任务]
        MemoryTool[memory<br/>记忆管理]
    end
    
    classDef layer fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef component fill:#f3e5f5,stroke:#4a148c,stroke-width:1px;
    classDef user fill:#fff3e0,stroke:#e65100,stroke-width:2px;
    
    class Channels,Gateway,Agent,Model,Execution layer;
    class Web,Telegram,Feishu,Webhook,Auth,RateLimit,Router,Security,Workspace,Loop,Memory,OpenRouter,Anthropic,OpenAI,Ollama,Terminal,File,Browser,Web,Delegate,Cronjob,MemoryTool component;
    class User user;
```

## 核心特性

| 特性 | 说明 |
|------|------|
| 🎭 可调人格 | honesty/humor/initiative/empathy 四参数实时调节 |
| 🧠 三层记忆 V3 | Core Memory（4 块固定区块注入 system prompt）+ Archival Memory（embedding 检索 + Ebbinghaus 衰减）+ Reflector（异步沉淀） |
| 🔌 模块化工具 | 自动发现，按需注册，安全隔离 |
| 🔀 Provider 抽象 | 不绑定特定 LLM，随时切换 |
| 🌐 多通道支持 | Web、Telegram、飞书、钉钉、Webhook |
| ⚡ 流式输出 | 实时响应，流畅交互 |

## 技术栈概览

```mermaid
mindmap
  root((TARS))
    前端
      React 18
      TypeScript
      Vite
      TailwindCSS
      Zustand
      React Router
      WebSocket
    后端
      FastAPI
      Python 3.11+
      asyncio
      SQLite
      FTS5
    模型
      OpenRouter
      Anthropic
      OpenAI
      Ollama
```

## 工作区结构

```mermaid
graph LR
    AgentDir[~/.tars/agents/{agent_id}/] --> SOUL[SOUL.md<br/>人格定义]
    AgentDir --> AGENTS[AGENTS.md<br/>行动规则]
    AgentDir --> Skills[skills/<br/>技能目录]

    DB[(SQLite)] --> CoreBlocks[core_memory_blocks<br/>persona/user_profile/<br/>project_context/working_principles]
    DB --> Archival[archival_memory<br/>embedding 检索 + 衰减]

    classDef dir fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef file fill:#fff3e0,stroke:#e65100,stroke-width:1px;
    classDef store fill:#e3f2fd,stroke:#1565c0,stroke-width:1px;

    class AgentDir dir;
    class SOUL,AGENTS,Skills file;
    class DB,CoreBlocks,Archival store;
```

> 记忆系统 V3：原 `MEMORY.md` / `USER.md` 已迁移到数据库 — Core Memory 的 `persona` / `user_profile` / `project_context` / `working_principles` 4 块区块由 Agent 自主通过 `core_memory_append` / `core_memory_replace` 编辑，Reflector 兜底每轮触发；长期事实进入 Archival Memory 通过 embedding 检索召回。

---

*文档版本: v1.0*  
*创建日期: 2026-05-05*
