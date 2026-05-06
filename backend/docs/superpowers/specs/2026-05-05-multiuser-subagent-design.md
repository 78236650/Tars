# 多用户权限与子代理系统设计文档

## 1. 概述

本设计文档描述了 TARS AI Agent 系统中多用户权限管理和子代理(subagent)功能的实现方案，包括完整的后端逻辑和前端配置界面设计。

### 1.1 设计目标

| 目标 | 说明 |
|------|------|
| 多用户支持 | 支持多个独立用户使用系统，每个用户有独立的数据和权限 |
| 角色权限 | 实现 admin/user/guest 三级角色权限系统 |
| 细粒度权限 | 基于资源的访问控制，用户只能访问自己的会话和数据 |
| 子代理委派 | 主代理可以将任务委派给专业子代理处理 |
| 多代理协作 | 多个子代理可以协作完成复杂任务 |
| 人格融合 | 子代理继承主代理人格特质，可配置融合权重 |
| 独立模型 | 子代理可配置独立的 LLM 模型 |
| 统一配置 | 前后端一体化配置界面，无系统割裂 |

---

## 2. 后端逻辑设计

### 2.1 权限系统

#### 2.1.1 角色定义

| 角色 | 权限说明 |
|------|----------|
| **admin** | 完整系统权限：管理用户、修改配置、访问所有会话和技能 |
| **user** | 标准用户权限：创建会话、使用技能、访问自己的历史记录 |
| **guest** | 受限权限：临时会话、部分技能可用、无持久化存储 |

#### 2.1.2 资源权限矩阵

| 资源类型 | 操作 | admin | user | guest |
|---------|------|-------|------|-------|
| session | create | ✅ | ✅ | ✅(临时) |
| session | read (own) | ✅ | ✅ | ❌ |
| session | read (others) | ✅ | ❌ | ❌ |
| session | delete (own) | ✅ | ✅ | ❌ |
| session | delete (others) | ✅ | ❌ | ❌ |
| skill | list | ✅ | ✅ | ✅(部分) |
| skill | activate/deactivate | ✅ | ❌ | ❌ |
| skill | create/update/delete | ✅ | ❌ | ❌ |
| model | list | ✅ | ✅ | ✅ |
| model | switch | ✅ | ✅ | ❌ |
| user | create/update/delete | ✅ | ❌ | ❌ |
| memory | access | ✅ | ✅(own) | ❌ |
| personality | read/write | ✅ | ✅(own) | ❌ |
| subagent | configure | ✅ | ✅ | ❌ |

#### 2.1.3 新增文件

| 文件 | 职责 |
|------|------|
| `tars/gateway/permission.py` | 权限管理和验证逻辑 |
| `tars/database/user_store.py` | 用户数据持久化存储 |

#### 2.1.4 核心代码结构

```python
# tars/gateway/permission.py
class UserRole(Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"

class PermissionManager:
    PERMISSIONS = {
        "session": {
            "create": [UserRole.ADMIN, UserRole.USER, UserRole.GUEST],
            "read_own": [UserRole.ADMIN, UserRole.USER],
            "read_others": [UserRole.ADMIN],
            "delete_own": [UserRole.ADMIN, UserRole.USER],
            "delete_others": [UserRole.ADMIN],
        },
        # ... 更多权限定义
    }
    
    def check_permission(self, user_role: UserRole, resource: str, action: str) -> bool:
        """检查权限"""
        if resource not in self.PERMISSIONS:
            return False
        if action not in self.PERMISSIONS[resource]:
            return False
        return user_role in self.PERMISSIONS[resource][action]
```

### 2.2 子代理系统

#### 2.2.1 子代理类型

| 子代理类型 | 专业领域 | 职责描述 |
|-----------|---------|----------|
| **CodeAgent** | 代码编写与调试 | 编写、测试、调试代码 |
| **WritingAgent** | 写作与编辑 | 撰写文章、文档、邮件 |
| **DataAgent** | 数据分析与可视化 | 处理数据、生成图表 |
| **ResearchAgent** | 信息检索 | 搜索、整理、汇总信息 |
| **PlanAgent** | 规划与组织 | 制定计划、任务分解 |

#### 2.2.2 子代理配置

```python
# tars/agent/subagents/base.py
class SubAgentConfig:
    type: SubAgentType
    name: str
    description: str
    llm_model: Optional[str] = None  # None = 继承主代理模型
    llm_provider: Optional[str] = None  # ollama/openrouter
    temperature: float = 0.7
    personality_weight: float = 0.5  # 人格融合权重(0-1)
    enabled: bool = True
```

#### 2.2.3 人格融合机制

```python
def merge_prompts(
    master_personality: Soul,
    subagent_prompt: str,
    weight: float = 0.5
) -> str:
    """融合主代理人格和子代理专业提示词"""
    personality_str = "\n".join([
        f"- {key}: {value}" 
        for key, value in vars(master_personality.parameters).items()
    ])
    
    return f"""你是一位专业的助手。

## 人格特质（权重: {weight}）
{personality_str}

## 专业领域
{subagent_prompt}

## 人格融合规则
- 你的回答风格应该是人格特质和专业领域的结合
- 人格权重决定了人格特质的影响程度
"""
```

#### 2.2.4 新增文件

| 文件 | 职责 |
|------|------|
| `tars/agent/subagents/__init__.py` | 子代理模块导出 |
| `tars/agent/subagents/base.py` | 子代理抽象基类 |
| `tars/agent/subagents/code.py` | 代码子代理实现 |
| `tars/agent/subagents/writing.py` | 写作子代理实现 |
| `tars/agent/subagents/data.py` | 数据分析子代理实现 |
| `tars/agent/subagents/research.py` | 研究子代理实现 |
| `tars/agent/subagents/plan.py` | 规划子代理实现 |
| `tars/agent/subagent_manager.py` | 子代理管理器 |

### 2.3 人格参数扩展

#### 2.3.1 扩展后的人格参数

```python
class SoulParameters:
    # 原有参数
    honesty: float = 0.9      # 诚实度 (0-1)
    humor: float = 0.5        # 幽默感 (0-1)
    initiative: float = 0.7   # 主动性 (0-1)
    empathy: float = 0.8      # 同理心 (0-1)
    
    # 新增参数
    formality: float = 0.5    # 正式程度 (0=随意, 1=正式)
    creativity: float = 0.6   # 创造力 (0-1)
    conciseness: float = 0.7   # 简洁度 (0=详细, 1=简洁)
    technical_depth: float = 0.5  # 技术深度 (0=通俗, 1=专业)
    curiosity: float = 0.6    # 好奇心 (0-1)
    skepticism: float = 0.3   # 怀疑度 (0=轻信, 1=谨慎)
```

#### 2.3.2 人格类型预设

| 人格类型 | 参数配置 | 适用场景 |
|----------|----------|----------|
| **专业助手** | formality=0.8, technical_depth=0.8 | 技术咨询、代码帮助 |
| **友好伙伴** | empathy=0.9, humor=0.7 | 日常聊天、情感支持 |
| **创意专家** | creativity=0.9, curiosity=0.8 | 写作、头脑风暴 |
| **严谨学者** | skepticism=0.8, conciseness=0.8 | 学术研究、数据分析 |
| **随和朋友** | formality=0.2, humor=0.8 | 休闲聊天、娱乐 |

---

## 3. 前端配置界面设计

### 3.1 前端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue.js | 3.x | 前端框架 |
| TypeScript | 5.x | 类型安全 |
| TailwindCSS | 3.x | 样式框架 |
| Pinia | 2.x | 状态管理 |
| Axios | 1.x | HTTP 客户端 |

### 3.2 前端目录结构

```
frontend/
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.vue
│   │   │   └── Header.vue
│   │   ├── auth/
│   │   │   ├── LoginForm.vue
│   │   │   └── UserProfile.vue
│   │   ├── settings/
│   │   │   ├── PersonalitySettings.vue  # 人格设置
│   │   │   ├── PermissionSettings.vue   # 权限管理
│   │   │   └── SubAgentSettings.vue     # 子代理配置
│   │   └── chat/
│   │       └── ChatPanel.vue
│   ├── views/
│   │   ├── ChatView.vue
│   │   ├── SettingsView.vue
│   │   └── AdminView.vue
│   ├── stores/
│   │   ├── auth.ts
│   │   ├── settings.ts
│   │   └── chat.ts
│   ├── api/
│   │   ├── auth.ts
│   │   ├── settings.ts
│   │   └── chat.ts
│   └── types/
│       └── index.ts
├── public/
├── package.json
├── vite.config.ts
└── tailwind.config.js
```

### 3.3 核心组件设计

#### 3.3.1 人格设置组件

**功能特性：**
- 人格类型选择（预设模板 + 自定义）
- 10项人格参数滑块调节
- 沟通风格文本配置
- 行为规则管理
- 实时预览效果

**布局：**
```
┌─────────────────────────────────────┐
│         人格设置                     │
├─────────────────────────────────────┤
│  ┌───────────────────────────────┐  │
│  │ 人格类型: [专业助手 ▼]        │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ 诚实度: [=====     ] 0.9      │  │
│  │ 幽默感: [===       ] 0.5      │  │
│  │ 主动性: [======    ] 0.7      │  │
│  │ 同理心: [=======   ] 0.8      │  │
│  │ 正式程度: [====     ] 0.5      │  │
│  │ 创造力: [======    ] 0.6      │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ 沟通风格: [textarea]          │  │
│  └───────────────────────────────┘  │
│                                     │
│  [保存设置]  [重置]  [预览效果]     │
└─────────────────────────────────────┘
```

#### 3.3.2 子代理配置组件

**功能特性：**
- 5种子代理卡片展示
- 独立模型选择
- 人格权重调节
- 温度参数设置
- 启用/停用开关

**布局：**
```
┌─────────────────────────────────────────────────────────┐
│                    子代理配置                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ 代码助手 │ │ 写作助手 │ │ 数据助手 │ │ 研究助手 │   │
│  │  🖥️     │ │  ✍️      │ │  📊      │ │  🔍      │   │
│  │ 模型:    │ │ 模型:    │ │ 模型:    │ │ 模型:    │   │
│  │ [codellama│ │ [llama3  │ │ [继承主  │ │ [gpt-4   │   │
│  │  :7b ▼]  │ │  :70b ▼] │ │ 代理 ▼]  │ │    ▼]    │   │
│  │ 人格权重: │ │ 人格权重: │ │ 人格权重: │ │ 人格权重: │   │
│  │ [===  ]  │ │ [===== ]  │ │ [====  ]  │ │ [===  ]  │   │
│  │ 温度:    │ │ 温度:    │ │ 温度:    │ │ 温度:    │   │
│  │ [==    ] │ │ [====  ] │ │ [===   ] │ │ [===   ] │   │
│  │ [停用]   │ │ [停用]   │ │ [停用]   │ │ [停用]   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│                                                         │
│  [保存配置]                                              │
└─────────────────────────────────────────────────────────┘
```

#### 3.3.3 用户管理组件

**功能特性：**
- 用户列表展示（用户名、邮箱、角色、创建时间）
- 角色切换下拉框
- 删除用户操作
- 添加新用户表单

**布局：**
```
┌──────────────────────────────────────────────────────────┐
│                      用户管理                           │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────┬──────────┬────────┬─────────────┬────────┐   │
│  │ 用户名 │ 邮箱      │ 角色   │ 创建时间    │ 操作   │   │
│  ├────────┼──────────┼────────┼─────────────┼────────┤   │
│  │ admin  │ admin@.. │ [admin │ 2026-05-01 │ [删除] │   │
│  │        │          │    ▼]   │             │        │   │
│  │ user1  │ user@... │ [user  │ 2026-05-02 │ [删除] │   │
│  │        │          │    ▼]   │             │        │   │
│  └────────┴──────────┴────────┴─────────────┴────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 添加用户:                                        │    │
│  │ 用户名: [________] 邮箱: [________] 角色: [▼]   │    │
│  │ [创建用户]                                       │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

---

## 4. API 接口设计

### 4.1 用户管理接口

| 接口 | 方法 | 路径 | 权限 | 描述 |
|------|------|------|------|------|
| 获取当前用户 | GET | `/api/users/me` | all | 获取当前登录用户信息 |
| 获取用户列表 | GET | `/api/users` | admin | 获取所有用户列表 |
| 创建用户 | POST | `/api/users` | admin | 创建新用户 |
| 更新用户 | PUT | `/api/users/{id}` | admin/own | 更新用户信息 |
| 删除用户 | DELETE | `/api/users/{id}` | admin | 删除用户 |
| 登录 | POST | `/api/auth/login` | all | 用户登录 |
| 登出 | POST | `/api/auth/logout` | all | 用户登出 |

### 4.2 人格设置接口

| 接口 | 方法 | 路径 | 权限 | 描述 |
|------|------|------|------|------|
| 获取人格设置 | GET | `/api/personality` | all | 获取当前人格配置 |
| 更新人格设置 | PUT | `/api/personality` | user+ | 更新人格配置 |
| 获取预设列表 | GET | `/api/personality/presets` | all | 获取人格预设列表 |
| 应用预设 | POST | `/api/personality/presets/{name}` | user+ | 应用指定预设 |

### 4.3 子代理接口

| 接口 | 方法 | 路径 | 权限 | 描述 |
|------|------|------|------|------|
| 获取子代理列表 | GET | `/api/subagents` | all | 获取所有子代理配置 |
| 获取子代理详情 | GET | `/api/subagents/{type}` | all | 获取单个子代理配置 |
| 更新子代理配置 | PUT | `/api/subagents/{type}` | user+ | 更新子代理配置 |
| 调用子代理 | POST | `/api/subagents/{type}/invoke` | user+ | 直接调用子代理执行任务 |
| 获取任务状态 | GET | `/api/subagents/tasks/{task_id}` | own | 获取任务执行状态 |

### 4.4 响应格式

```json
{
  "success": true,
  "message": "操作成功",
  "data": { ... },
  "timestamp": "2026-05-05T10:30:00Z"
}
```

---

## 5. 数据库表设计

### 5.1 users 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PRIMARY KEY | 用户唯一标识 |
| username | TEXT | NOT NULL | 用户名 |
| email | TEXT | UNIQUE | 邮箱 |
| role | TEXT | NOT NULL | 角色 |
| api_key | TEXT | UNIQUE | API密钥 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| last_login | TIMESTAMP | | 最后登录时间 |

### 5.2 user_sessions 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| user_id | TEXT | FOREIGN KEY | 用户ID |
| session_id | TEXT | PRIMARY KEY | 会话ID |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |

### 5.3 subagent_config 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| user_id | TEXT | PRIMARY KEY | 用户ID |
| agent_type | TEXT | PRIMARY KEY | 子代理类型 |
| llm_model | TEXT | | LLM模型名称 |
| llm_provider | TEXT | | 模型提供者 |
| temperature | REAL | NOT NULL | 温度参数 |
| personality_weight | REAL | NOT NULL | 人格权重 |
| enabled | INTEGER | NOT NULL | 是否启用 |

### 5.4 subagent_tasks 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| task_id | TEXT | PRIMARY KEY | 任务ID |
| user_id | TEXT | NOT NULL | 用户ID |
| session_id | TEXT | NOT NULL | 会话ID |
| agent_type | TEXT | NOT NULL | 子代理类型 |
| input | TEXT | NOT NULL | 任务输入 |
| output | TEXT | | 任务输出 |
| status | TEXT | NOT NULL | 任务状态 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| completed_at | TIMESTAMP | | 完成时间 |

---

## 6. 状态管理设计

### 6.1 前端状态结构

```typescript
// stores/auth.ts
interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
}

// stores/settings.ts
interface SettingsState {
  personality: Personality;
  subagents: SubAgent[];
  availableModels: string[];
  presets: PersonalityPreset[];
}

interface Personality {
  identity: {
    name: string;
    role: string;
    creator: string;
  };
  parameters: {
    honesty: number;
    humor: number;
    initiative: number;
    empathy: number;
    formality: number;
    creativity: number;
    conciseness: number;
    technicalDepth: number;
    curiosity: number;
    skepticism: number;
  };
  communicationStyle: string;
  behaviorRules: string[];
}

interface SubAgent {
  type: string;
  name: string;
  description: string;
  icon: string;
  enabled: boolean;
  llmModel: string | null;
  llmProvider: string | null;
  personalityWeight: number;
  temperature: number;
}
```

---

## 7. 系统集成方案

### 7.1 前后端数据流

```
前端配置界面 → API 请求 → FastAPI → PermissionManager → 业务逻辑 → 数据库
     ↓                                                         ↑
     ←←←←←←←←←←←←←←←←←← 响应数据 ←←←←←←←←←←←←←←←←←←←←←←←←
```

### 7.2 关键集成点

| 集成点 | 说明 |
|--------|------|
| **权限验证** | 前端请求携带 API Key，后端 Gateway 层验证 |
| **实时更新** | 配置更新后立即生效，无需重启 |
| **状态同步** | 使用 WebSocket 监听配置变更 |
| **错误处理** | 统一的错误响应格式和处理机制 |

### 7.3 安全性考虑

| 安全措施 | 说明 |
|----------|------|
| API Key 保护 | 存储在 HttpOnly Cookie 或 Authorization Header |
| 输入验证 | 前端和后端双重验证 |
| 权限检查 | 后端每次关键操作检查权限 |
| 日志记录 | 记录所有权限检查失败和异常操作 |

---

## 8. 测试计划

### 8.1 权限系统测试

| 测试场景 | 描述 |
|----------|------|
| admin 访问所有资源 | 验证管理员可以访问所有会话和用户 |
| user 访问自己的会话 | 验证用户只能访问自己创建的会话 |
| guest 受限访问 | 验证访客只能创建临时会话 |
| 权限拒绝 | 验证用户无法访问他人资源 |

### 8.2 子代理系统测试

| 测试场景 | 描述 |
|----------|------|
| 任务委派 | 验证主代理可以将任务委派给子代理 |
| 人格融合 | 验证子代理响应受人格参数影响 |
| 独立模型 | 验证子代理可以使用独立模型 |
| 多代理协作 | 验证多个子代理可以协作完成任务 |

### 8.3 前端界面测试

| 测试场景 | 描述 |
|----------|------|
| 人格设置保存 | 验证人格参数正确保存到后端 |
| 子代理配置更新 | 验证子代理配置正确更新 |
| 用户管理操作 | 验证用户创建、编辑、删除功能 |
| 权限控制 | 验证非管理员无法访问管理功能 |

---

## 9. 部署与集成

### 9.1 依赖关系

```
Gateway → AuthManager → PermissionManager → UserStore → Database
    ↓
MasterAgent → SubAgentManager → SubAgents
    ↓
FastAPI API层 → 前端界面
```

### 9.2 配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| REQUIRE_AUTH | 是否启用认证 | false |
| GUEST_ENABLED | 是否允许访客模式 | true |
| MAX_SUBAGENTS | 最大子代理数量 | 10 |
| DEFAULT_PERSONALITY | 默认人格类型 | professional |

---

## 10. 代码规范

### 10.1 文件结构

```
tars/
├── gateway/
│   ├── auth.py          # 身份验证
│   ├── permission.py    # 权限管理（新增）
│   └── ...
├── database/
│   ├── user_store.py    # 用户存储（新增）
│   └── ...
├── agent/
│   ├── base.py          # 主代理
│   ├── subagent_manager.py  # 子代理管理器（新增）
│   └── subagents/       # 子代理模块（新增）
│       ├── __init__.py
│       ├── base.py
│       ├── code.py
│       ├── writing.py
│       ├── data.py
│       ├── research.py
│       └── plan.py
└── ...
```

### 10.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 类名 | PascalCase | `PermissionManager`, `CodeAgent` |
| 方法名 | snake_case | `check_permission()`, `delegate_task()` |
| 变量名 | snake_case | `user_id`, `agent_type` |
| 枚举名 | PascalCase | `UserRole`, `SubAgentType` |

---

## 11. 未来扩展

### 11.1 可扩展功能

| 功能 | 说明 |
|------|------|
| 用户组 | 支持用户分组和组权限继承 |
| 角色定制 | 支持自定义角色和权限配置 |
| 子代理市场 | 支持第三方子代理插件 |
| 任务队列 | 支持异步任务处理和队列管理 |
| 人格共享 | 支持导出/导入人格配置 |

---

**文档版本**: v2.0  
**创建日期**: 2026-05-05  
**作者**: TARS Team  
**状态**: 设计完成，待审核