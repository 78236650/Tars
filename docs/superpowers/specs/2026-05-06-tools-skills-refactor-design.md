# Tools & Skills 系统全面重构设计

## 概述

重构 TARS 的工具（Tools）和技能（Skills）系统，解决当前架构中的核心问题：
- 多个注册中心各管各的，同一工具需注册三次
- Tool Calling 依赖正则匹配关键词而非 LLM Function Calling
- Skill 只是描述文件不能真正执行
- SkillHub 是硬编码假实现
- 工具重复（FileTool vs FileReadTool, TerminalTool vs CommandTool）

## 架构方案：Tool 层 + Skill 层分离，通过 Dispatcher 桥接

### 核心概念

- **Tool** = 原子能力，有 `execute()` 方法和 JSON Schema 参数定义
- **Skill** = 高层能力，两种类型：
  - `PluginSkill`：包含 Python 代码，加载后注册为 Tool
  - `PromptSkill`：包含 Prompt 模板，执行时注入 LLM 上下文
- **SkillHub** = 外部市场（GitHub Releases 作为数据源），下载的包解析为 Skill
- **ToolDispatcher** = 统一调度器，支持 LLM 原生 Function Calling + Prompt Fallback

### 调用关系

```
Agent → ToolDispatcher (function calling / prompt fallback)
             ↓
        ToolRegistry (唯一注册中心)
             ├── BuiltinTool (weather, file, command, memory, cronjob, web)
             ├── PluginSkill → 加载 Python 插件 → 注册为 Tool
             └── PromptSkill → 注入 system prompt → LLM 处理

SkillHub (GitHub Releases) → 下载 → 校验 → 解压 → 注册为 PluginSkill 或 PromptSkill
```

## 后端目录结构

```
tars/
├── tools/                      # 工具层（替代原 execution/）
│   ├── __init__.py
│   ├── base.py                 # BaseTool, ToolResult, ToolSchema
│   ├── registry.py             # ToolRegistry（唯一注册中心）
│   ├── dispatcher.py           # ToolDispatcher（function calling + prompt fallback）
│   ├── builtin/                # 内置工具
│   │   ├── __init__.py
│   │   ├── weather.py
│   │   ├── file.py             # 合并 file.py + local.py 的文件操作
│   │   ├── command.py          # 合并 terminal.py + local.py 的命令执行
│   │   ├── memory.py
│   │   ├── cronjob.py
│   │   └── web.py
│   └── plugin_loader.py        # Python 插件动态加载器
├── skills/                     # 技能层
│   ├── __init__.py
│   ├── base.py                 # Skill, PluginSkill, PromptSkill
│   ├── registry.py             # SkillRegistry
│   ├── loader.py               # 从目录加载 Skill
│   └── executor.py             # Skill → Tool 的桥接
├── skillhub/                   # SkillHub 市场
│   ├── __init__.py
│   ├── client.py               # GitHub Releases API 客户端
│   ├── installer.py            # 下载、校验、安装
│   └── models.py               # 数据模型
├── api/                        # API 路由
│   ├── __init__.py
│   ├── tools.py                # /api/tools/
│   ├── skills.py               # /api/skills/
│   └── skillhub.py             # /api/skillhub/
```

### 删除的文件

- `execution/` 整个目录（迁移到 `tools/`）
- `agent/tool_calling.py`（迁移到 `tools/dispatcher.py`）
- 旧 `skills/` 目录内容（重写）

## 核心模块设计

### 1. BaseTool & ToolResult

```python
@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class BaseTool(ABC):
    name: str
    description: str
    parameters_schema: Dict[str, Any]  # JSON Schema

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass

    def to_function_schema(self) -> Dict[str, Any]:
        """转换为 OpenAI function calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema
            }
        }
```

### 2. ToolRegistry

```python
class ToolRegistry:
    """唯一的工具注册中心"""

    def register(self, tool: BaseTool) -> None
    def unregister(self, name: str) -> None
    def get(self, name: str) -> Optional[BaseTool]
    def list_all(self) -> List[BaseTool]
    def get_function_schemas(self) -> List[Dict[str, Any]]
```

### 3. ToolDispatcher

```python
class ToolDispatcher:
    """统一工具调度器，处理 LLM 与工具的交互循环"""

    def __init__(self, registry: ToolRegistry, provider: LLMProvider):
        ...

    async def chat_with_tools(
        self,
        messages: List[ChatMessage],
        stream: bool = True,
        on_tool_call: Optional[Callable] = None,   # 工具调用回调
        on_tool_result: Optional[Callable] = None,  # 工具结果回调
        max_tool_rounds: int = 5
    ) -> AsyncGenerator[str, None]:
        """带工具调用的对话"""
        ...

    def _supports_native_tools(self) -> bool:
        """检测当前 model 是否支持原生 function calling"""
        ...

    def _build_tool_prompt(self) -> str:
        """为不支持 function calling 的模型构建工具提示"""
        ...

    def _parse_tool_call_from_text(self, text: str) -> Optional[Tuple[str, Dict]]:
        """从文本中解析 JSON 格式的工具调用（fallback 模式）"""
        ...
```

**调用流程**：
```
1. 收集 ToolRegistry 中所有工具的 function schema
2. 判断模型是否支持原生 function calling
   - 支持：传 tools 参数给 LLM API
   - 不支持：将工具描述注入 system prompt，引导输出 JSON
3. 发送请求给 LLM
4. 解析响应：
   - 如果包含 tool_calls → 执行工具 → 将结果作为 tool message 回传 → 回到步骤 3
   - 如果是普通文本 → 流式输出给用户
5. 最多循环 max_tool_rounds 轮
```

### 4. Skill 系统

```python
class SkillType(Enum):
    PLUGIN = "plugin"
    PROMPT = "prompt"

@dataclass
class SkillParameter:
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Optional[Any] = None

@dataclass
class Skill:
    id: str
    name: str
    description: str
    type: SkillType
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    source: str = "local"  # "local" | "skillhub"
    permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    # PluginSkill
    entry_point: Optional[str] = None
    # PromptSkill
    prompt_template: Optional[str] = None
    parameters: List[SkillParameter] = field(default_factory=list)
```

**Skill 包目录格式**：
```
skills/
├── weather/
│   ├── skill.yaml          # 元数据
│   └── main.py             # BaseTool 实现
├── calculator/
│   ├── skill.yaml
│   └── main.py
└── writing-assistant/
    └── skill.yaml          # type: prompt，含 prompt_template
```

**skill.yaml 示例（PluginSkill）**：
```yaml
id: weather
name: 天气查询
description: 查询全球城市的实时天气和天气预报
type: plugin
version: "1.0.0"
author: TARS
tags: [weather, forecast, utility]
entry_point: main.py
permissions:
  - network
```

**skill.yaml 示例（PromptSkill）**：
```yaml
id: writing-assistant
name: 写作助手
description: 帮助润色文字、调整语气和风格
type: prompt
version: "1.0.0"
author: TARS
tags: [writing, creative]
prompt_template: |
  你现在是一个专业写作助手。请帮助用户：
  - 润色文字，提升表达质量
  - 调整语气和风格
  - 检查语法和逻辑
parameters:
  - name: style
    type: string
    description: 写作风格
    default: professional
```

**加载机制**：
- PluginSkill：动态 import `main.py`，实例化 Tool 类，注册到 ToolRegistry
- PromptSkill：不注册为 Tool，在对话时将 prompt_template 追加到 system prompt

### 5. SkillHub（GitHub Releases 数据源）

**SkillHubClient** — 通过 GitHub API 搜索和获取 Skill 包：

```python
class SkillHubClient:
    """通过 GitHub Releases 作为远程数据源"""

    def __init__(self, org: str = "tars-skillhub", topic: str = "tars-skill"):
        ...

    async def search(self, query: str) -> List[SkillHubPackage]:
        """搜索带有 tars-skill topic 的仓库"""

    async def get_detail(self, repo: str) -> SkillHubPackage:
        """获取单个仓库的最新 Release 详情"""

    async def download(self, repo: str, version: str = "latest") -> Path:
        """下载 Release 的 tar.gz 包到临时目录"""
```

**SkillInstaller** — 安装/卸载/更新：

```python
class SkillInstaller:
    def __init__(self, skills_dir: Path, client: SkillHubClient):
        ...

    async def install(self, repo: str) -> Skill:
        """下载 → 校验 checksum → 解压到 skills/ → 加载 → 注册"""

    async def uninstall(self, skill_id: str) -> bool
    async def update(self, skill_id: str) -> Skill
    def list_installed(self) -> List[Skill]
    async def check_updates(self) -> List[Dict[str, str]]
```

**安全措施**：
- 下载后校验 Release 附带的 SHA256 checksum
- PluginSkill 代码在受限环境执行（限制危险 import）
- 安装前必须确认权限声明（network/file_read/command_exec 等）

**Skill 包格式**（tar.gz）：
```
package.tar.gz
├── skill.yaml
├── main.py            # PluginSkill 的代码（可选）
├── README.md          # 说明文档（可选）
└── requirements.txt   # Python 依赖（可选）
```

## 后端 API 重构

**新的 API 结构**：

```
/api/tools/                     # 工具管理
├── GET    /                    # 列出所有工具
├── GET    /{id}                # 工具详情
├── PUT    /{id}/config         # 更新配置
├── PUT    /{id}/status         # 启用/禁用
├── DELETE /{id}                # 删除（仅非内置）
└── POST   /execute             # 手动执行（调试用）

/api/skills/                    # 技能管理
├── GET    /                    # 列出已安装
├── POST   /upload              # 上传本地 Skill 包
├── POST   /create-prompt       # 创建 PromptSkill
├── DELETE /{id}                # 卸载
└── POST   /reload              # 重新加载

/api/skillhub/                  # SkillHub 商店
├── GET    /search?q=xxx        # 搜索
├── GET    /detail/{id}         # 包详情
├── POST   /install             # 安装
├── POST   /uninstall           # 卸载
├── GET    /installed           # 已安装列表
└── GET    /updates             # 检查更新
```

**删除的路由**：
- `/api/skills/execute`
- `/api/skills/tools/list`
- `/api/skillhub/repos`
- `/api/skillhub/load`
- `/api/tools/skillhub/*`
- `/api/tools/templates`
- `/api/debug/parse`

**main.py 瘦身**：只保留应用初始化、中间件、WebSocket、启动/关闭事件。业务路由通过 `include_router` 引入。

## Agent 消息处理流程重构

**新流程**：

```python
async def handle_message(self, session_id, user_content, channel):
    # 1. 保存用户消息、获取历史
    # 2. 构建 system prompt（含人格 + 记忆 + 激活的 PromptSkill）
    # 3. 调用 ToolDispatcher.chat_with_tools()
    #    - 内部处理 function calling 循环
    #    - 通过 channel 推送工具调用事件
    #    - 支持多轮工具调用直到 LLM 给出最终回答
    # 4. 流式输出最终回答
    # 5. 提取记忆
```

**WebSocket 事件类型**：

| 事件类型 | 说明 |
|---------|------|
| `text_chunk` | LLM 流式文本（已有） |
| `tool_calling` | LLM 决定调用工具（含 tool_name + parameters） |
| `tool_result` | 工具执行结果（含 success + output） |
| `done` | 对话完成（已有） |
| `error` | 错误（已有） |

## 前端改动

### ToolsView.vue — Tab 分区布局

```
┌─────────────────────────────────────────────────┐
│  Tools 管理中心            [+ 添加] [浏览商店]    │
├─────────────────────────────────────────────────┤
│  [内置工具] [已安装技能] [SkillHub 商店]          │
├─────────────────────────────────────────────────┤
│  Tab 1: 内置工具（不可删除，可启用/禁用/配置）     │
│  Tab 2: 已安装技能（显示类型 + 来源标签）          │
│  Tab 3: SkillHub 商店（内嵌浏览，不再是弹窗）      │
└─────────────────────────────────────────────────┘
```

SkillHub 从弹窗升级为独立 Tab，支持搜索、分类浏览、权限声明展示、版本信息。

### ToolCard.vue — 增强展示

新增标签：
- `type`：`Tool` / `Plugin` / `Prompt`
- `source`：`内置` / `本地` / `SkillHub`
- SkillHub 来源显示版本号

### ToolDetailModal.vue — 按类型分化

- PluginSkill：显示参数 Schema、权限声明、依赖列表
- PromptSkill：显示可编辑的 Prompt 模板预览
- SkillHub 来源：显示更新按钮、作者、GitHub 链接

### AddToolModal.vue — 重做

三种添加方式：
1. 上传 Skill 包（`.tar.gz` 或目录）
2. 在线创建 PromptSkill（编辑 name/description/template）
3. 生成 PluginSkill 脚手架代码

### ChatPanel.vue — 工具调用可视化

聊天面板新增工具调用折叠卡片：
```
┌──────────────────────────────────────┐
│ 🔧 调用 Weather 工具              ▼  │
│ 参数: {"city": "上海"}                │
│ ────────────────────────────────     │
│ 结果: 🌤️ 上海 22°C 多云               │
└──────────────────────────────────────┘
```

多轮工具调用按顺序展示调用链。

### 类型定义更新（types/index.ts）

```typescript
export interface Tool {
  id: string
  name: string
  icon: string
  type: 'builtin' | 'plugin' | 'prompt'
  source: 'builtin' | 'local' | 'skillhub'
  status: 'active' | 'disabled'
  description: string
  version?: string
  author?: string
  permissions?: string[]
  parameters_schema?: Record<string, any>
}

export interface SkillHubPackage {
  id: string
  name: string
  description: string
  author: string
  version: string
  downloads: number
  type: 'plugin' | 'prompt'
  tags: string[]
  permissions: string[]
  github_url: string
}

export interface ToolCallEvent {
  tool: string
  parameters: Record<string, any>
  result?: { success: boolean; output: string }
  timestamp: string
}
```

### API 层（api/index.ts）

```typescript
export const toolsApi = {
  listTools: () => api.get('/tools'),
  getToolDetail: (id: string) => api.get(`/tools/${id}`),
  updateToolConfig: (id: string, config: any) => api.put(`/tools/${id}/config`, config),
  toggleToolStatus: (id: string, status: string) =>
    api.put(`/tools/${id}/status`, { status }),
  deleteTool: (id: string) => api.delete(`/tools/${id}`),
}

export const skillsApi = {
  listSkills: () => api.get('/skills'),
  uploadSkill: (file: File) => api.post('/skills/upload', formData),
  createPromptSkill: (data: any) => api.post('/skills/create-prompt', data),
  uninstallSkill: (id: string) => api.delete(`/skills/${id}`),
}

export const skillhubApi = {
  search: (query: string) => api.get('/skillhub/search', { params: { query } }),
  getDetail: (id: string) => api.get(`/skillhub/detail/${id}`),
  install: (id: string) => api.post('/skillhub/install', { skill_id: id }),
  uninstall: (id: string) => api.post('/skillhub/uninstall', { skill_id: id }),
  checkUpdates: () => api.get('/skillhub/updates'),
}
```

## 迁移策略

分 6 个阶段实施，每阶段可独立测试：

1. **Phase 1**：新建 `tools/`，实现 `BaseTool`、`ToolRegistry`、`ToolDispatcher`，迁移内置工具
2. **Phase 2**：实现 Skill 系统（`skill.yaml`、PluginSkill 加载、PromptSkill 注入）
3. **Phase 3**：实现 SkillHub（GitHub Releases 客户端、安装器、安全校验）
4. **Phase 4**：重构 `Agent.handle_message()`，接入 ToolDispatcher
5. **Phase 5**：重构 API 路由，更新前端页面
6. **Phase 6**：删除旧代码（`execution/`、`agent/tool_calling.py`、旧 `skills/`）

## 设计要点总结

**解决的核心问题**：

| 问题 | 解决方案 |
|------|---------|
| 多注册中心，重复注册 | 统一 ToolRegistry，PluginSkill 加载后注册到同一地方 |
| 正则匹配工具调用 | ToolDispatcher 用 LLM function calling，无原生支持时 prompt fallback |
| Skill 只是描述文件 | PluginSkill 动态加载 Python 代码；PromptSkill 注入 system prompt |
| SkillHub 假实现 | 基于 GitHub Releases 的真实客户端，支持 checksum 校验和权限声明 |
| FileTool 和 FileReadTool 重复 | 合并到 `tools/builtin/file.py`，统一接口 |
| TerminalTool 和 CommandTool 重复 | 合并到 `tools/builtin/command.py`，保留白名单保护 |
| 工具调用不支持多轮 | ToolDispatcher 支持 `max_tool_rounds` 轮的工具调用循环 |

**新增能力**：

- LLM Function Calling 原生支持（qwen3 等模型）
- PromptSkill 作为人格模板、角色扮演、工作流
- SkillHub 从 GitHub 安装社区技能包
- 权限声明 + 用户确认机制
- 工具调用可视化（聊天面板）
- Skill 依赖解析
- Skill 版本管理和更新检查

**保持不变的部分**：

- 人格系统（`workspace/soul.py`）
- 子代理系统（`agent/subagent_manager.py`）
- 记忆系统（`database/memory.py`、`workspace/memory.py`）
- 用户权限系统（`gateway/permission.py`）
- 自进化系统（`evolution/`）
- 定时任务调度（`scheduler.py`）

