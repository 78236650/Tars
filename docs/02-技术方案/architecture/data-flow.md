# TARS 数据流图

## 完整消息处理流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant Channel as Channels 通道层
    participant Gateway as Gateway 网关层
    participant Agent as Agent 智能体层
    participant Model as Model 模型层
    participant Execution as Execution 执行层
    participant Memory as 记忆系统

    User->>Channel: 发送消息
    Channel->>Channel: 标准化为 ChannelMessage
    Channel->>Gateway: 转发消息

    Gateway->>Gateway: 身份核验
    Gateway->>Gateway: 速率检查
    Gateway->>Gateway: 安全策略检查
    Gateway->>Agent: 路由到 Agent

    Agent->>Memory: 检索相关记忆
    Memory-->>Agent: 返回记忆
    Agent->>Agent: 加载工作区文件
    Agent->>Agent: 构建 System Prompt
    Agent->>Agent: 加载会话历史
    
    Agent->>Model: 调用 LLM (流式)
    
    loop Agent Loop
        Model-->>Agent: 流式文本 chunk
        Agent->>Channel: 推送 chunk
        Channel-->>User: 显示文本
        
        alt 工具调用
            Model-->>Agent: 工具调用指令
            Agent->>Execution: 执行工具
            Execution->>Execution: 安全检查
            Execution-->>Agent: 返回结果
            Agent->>Model: 追加工具结果
            Agent->>Model: 继续调用 LLM
        end
    end
    
    Model-->>Agent: 对话完成
    Agent->>Memory: 提取记忆
    Memory->>Memory: 保存到 MEMORY.md
    Memory->>Memory: 更新 SQLite 索引
    
    Agent-->>Gateway: 返回响应
    Gateway-->>Channel: 转发响应
    Channel-->>User: 显示完整响应
```

---

## 请求数据流（正常对话流程

```mermaid
flowchart TD
    Start([用户输入]) --> A[通道层处理]
    A --> B{身份核验?}
    B -->|否| Err1[返回 401]
    
    B -->|是| C{速率限制?}
    C -->|是| Err2[返回 429]
    
    C -->|否| D{安全检查?}
    D -->|拦截| Err3[拒绝操作]
    
    D -->|通过| E[加载工作区]
    E --> F[检索相关记忆]
    F --> G[构建 System Prompt]
    G --> H[加载会话历史]
    H --> I[调用 LLM 流式]
    
    I --> J{工具调用?}
    J -->|否| K[流式输出文本]
    J -->|是| L[执行工具]
    L --> M[安全检查]
    M -->|通过| N[执行操作]
    M -->|拦截| O[返回错误]
    N --> P[追加结果]
    P --> I
    
    K --> Q{对话结束?}
    Q -->|否| Wait((等待))
    Q -->|是| R[提取记忆]
    R --> S[保存 MEMORY.md]
    S --> T[更新 SQLite]
    T --> End([完成])
    
    Wait --> Start
    
    classDef error fill:#ffebee,stroke:#c62828,stroke-width:2px;
    classDef process fill:#e3f2fd,stroke:#1565c0,stroke-width:1px;
    
    class Err1,Err2,Err3,O error;
    class A,E,F,G,H,I,J,K,L,M,N,P,Q,R,S,T process;
```

---

## 工具执行数据流

```mermaid
graph TB
    Agent[Agent] -->|调用工具| Registry[ToolRegistry]
    Registry -->|查找工具| ToolCheck{工具存在?}
    ToolCheck -->|否| NotFound[工具不存在错误]
    
    ToolCheck -->|是| SecurityCheck{安全策略?}
    SecurityCheck -->|拦截| Reject[拒绝执行]
    
    SecurityCheck -->|通过| Execute[执行工具]
    
    Execute -->|成功| Success[返回结果]
    Execute -->|失败| Fail[返回错误]
    
    Success -->|结果| Agent
    Fail -->|错误| Agent
    Reject -->|错误| Agent
    NotFound -->|错误| Agent
    
    subgraph 安全检查项
        PathCheck{路径白名单?
        CmdCheck{命令黑名单?}
        RateCheck{工具调用频率?}
    end
    
    SecurityCheck --> PathCheck
    PathCheck --> CmdCheck
    CmdCheck --> RateCheck
```

---

## 记忆系统数据流

```mermaid
graph LR
    Agent -->|检索| Query[查询内容]
    Query --> SQLite[SQLite FTS5]
    SQLite -->|搜索| Index[全文索引]
    Index -->|返回| Results[相关记忆]
    Results --> Agent
    
    Agent -->|保存| Extract[提取记忆]
    Extract -->|写入| Markdown[MEMORY.md]
    Markdown -->|更新| Index
    
    Agent -->|会话结束| AutoExtract[自动提取]
    AutoExtract -->|调用| LLM[LLM 提取]
    LLM -->|写入| Markdown
    
    classDef storage fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef process fill:#fff3e0,stroke:#ef6c00,stroke-width:1px;
    
    class SQLite,Markdown,Index storage;
    class Query,Extract,AutoExtract,LLM process;
```

---

## 异常处理流程

```mermaid
graph TB
    Error[发生异常] --> Type{异常类型?}
    
    Type -->|认证失败| AuthErr[身份验证错误]
    AuthErr -->|返回| Resp1[401 Unauthorized]
    
    Type -->|超限| RateErr[速率限制错误]
    RateErr -->|返回| Resp2[429 Too Many Requests]
    
    Type -->|安全| SecurityErr[安全策略错误]
    SecurityErr -->|返回| Resp3[操作被拒绝]
    
    Type -->|工具| ToolErr[工具执行错误]
    ToolErr -->|重试?| Retry{可重试?}
    Retry -->|是| RetryExec[重试执行]
    Retry -->|否| Resp4[返回错误信息]
    
    Type -->|模型| ModelErr[模型调用错误]
    ModelErr -->|切换?| Switch{切换 Provider?}
    Switch -->|是| SwitchProv[切换 Provider]
    Switch -->|否| Resp5[返回错误信息]
    
    Type -->|其他| OtherErr[未知错误]
    OtherErr -->|记录| Log[记录日志]
    Log --> Resp6[返回通用错误]
    
    classDef error fill:#ffebee,stroke:#c62828,stroke-width:2px;
    classDef resp fill:#e3f2fd,stroke:#1565c0,stroke-width:1px;
    
    class AuthErr,RateErr,SecurityErr,ToolErr,ModelErr,OtherErr error;
    class Resp1,Resp2,Resp3,Resp4,Resp5,Resp6 resp;
```

---

*文档版本: v1.0*  
*创建日期: 2026-05-05*
