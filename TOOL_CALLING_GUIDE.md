# TARS 工具调用指南 (v2.0)

## 概述

TARS Agent 使用 **ToolDispatcher** 调度工具，支持两种调用模式：

1. **LLM 原生 Function Calling**（推荐）— 模型直接输出结构化的 tool_calls
2. **Prompt Fallback** — 不支持 function calling 的模型通过 prompt 引导输出 JSON

从 v1.0 的正则匹配升级到 v2.0 的标准 Function Calling 协议，工具调用更准确、可靠。

## 支持原生 Function Calling 的模型

```
qwen3, qwen2.5, qwen2
llama3.1, llama3.2, llama3.3
mistral, mixtral
command-r
gemma2
deepseek-chat, deepseek-coder
```

其他模型会自动降级为 Prompt Fallback 模式。

## 内置工具

| 工具 | 说明 |
|------|------|
| weather | 查询全球城市天气 |
| file | 读取本地文件 |
| file_list | 列出目录文件 |
| command | 执行白名单内的命令 |
| memory | 管理长期记忆 |
| cronjob | 管理定时任务 |
| web | 获取网页内容 |
| calculator | 数学计算（作为 PluginSkill 加载） |

## 调用流程

```
用户消息
    ↓
Agent.handle_message()
    ↓
ToolDispatcher.chat_with_tools()
    ↓
┌─ 支持 Function Calling ────────┐
│   LLM API 带 tools 参数         │
│   → 解析 tool_calls             │
├─ Prompt Fallback ──────────────┤
│   工具描述注入 system prompt    │
│   → 从文本解析 JSON             │
└────────────────────────────────┘
    ↓
执行工具 → 结果回传 LLM
    ↓
最多 max_rounds 轮（默认 5）
    ↓
流式输出最终回答
```

## WebSocket 事件

对话过程中前端会收到以下事件：

| 事件 | 说明 |
|------|------|
| `text_chunk` | LLM 流式文本 |
| `tool_calling` | LLM 决定调用工具（tool + parameters） |
| `tool_result` | 工具执行结果（success + output） |
| `warning` | 模型能力不足提示（如图片 OCR 降级） |
| `file_processing` | 文件正在解析中 |
| `done` | 对话完成 |
| `error` | 错误 |

## 工具管理 API

```
GET  /api/tools/            # 列出所有工具
GET  /api/tools/{id}        # 工具详情
PUT  /api/tools/{id}/status # 启用/禁用
POST /api/tools/execute     # 手动执行（调试用）
```

## 开发自定义工具

有两种方式：

### 方式 1：作为 PluginSkill 添加

在 `skills/` 目录下创建目录，编写 `skill.yaml` 和 `main.py`，参考 [SKILLS_GUIDE.md](SKILLS_GUIDE.md)。

### 方式 2：内置工具

在 `backend/tars/tools/builtin/` 下创建 Python 文件，继承 `BaseTool`：

```python
from tars.tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "工具描述，LLM 会根据这个判断何时调用"
    parameters_schema = {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "参数说明"}
        },
        "required": ["param1"]
    }

    async def execute(self, **kwargs) -> ToolResult:
        value = kwargs.get("param1")
        # 执行逻辑
        return ToolResult(success=True, output="结果")
```

然后在 `main.py` 中注册：

```python
from tars.tools.builtin import MyTool
tool_registry.register(MyTool())
```

## 调试工具调用

手动测试工具：

```bash
curl -X POST http://localhost:8000/api/tools/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "calculator", "parameters": {"expression": "2+3*4"}}'
```

## v1.0 → v2.0 变化

| v1.0 | v2.0 |
|------|------|
| 正则匹配用户输入关键词 | LLM Function Calling |
| 硬编码中文关键词 | 标准 JSON Schema |
| 单轮工具调用 | 多轮工具调用（最多 5 轮） |
| 工具散落在多个注册表 | 唯一 ToolRegistry |
| `ToolCaller.parse_tool_call()` | `ToolDispatcher.chat_with_tools()` |
