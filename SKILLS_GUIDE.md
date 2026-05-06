# TARS 技能系统指南 (v2.0)

## 概述

TARS 技能系统支持两种类型的技能：

- **PluginSkill** — Python 代码插件，加载后注册为可调用的 Tool
- **PromptSkill** — Prompt 模板，激活后注入 LLM 的 system prompt 增强行为

技能通过 `skill.yaml` 文件定义，存放在 `skills/` 目录下。

## 默认技能

| 技能 | 类型 | 说明 |
|------|------|------|
| calculator | Plugin | 安全的数学表达式求值（四则运算、三角函数、对数等） |
| code_assistant | Prompt | 代码编写/调试/审查/重构专家 |
| summarizer | Prompt | 结构化摘要提取 |
| translator | Prompt | 中英互译，保持语境和语气 |
| planner | Prompt | 任务分解、时间估算、优先级排序 |

## 技能目录结构

```
skills/
├── calculator/
│   ├── skill.yaml      # 元数据定义
│   └── main.py         # Python 实现（PluginSkill）
├── code_assistant/
│   └── skill.yaml      # 含 prompt_template（PromptSkill）
├── summarizer/
│   └── skill.yaml
├── translator/
│   └── skill.yaml
└── planner/
    └── skill.yaml
```

## skill.yaml 格式

### PluginSkill 示例

```yaml
id: calculator
name: 计算器
description: 精确的数学计算工具
type: plugin
version: "1.0.0"
author: TARS
tags: [math, calculator]
entry_point: main.py
permissions: []
```

`main.py` 中需要实现一个继承 `BaseTool` 的类：

```python
from tars.tools.base import BaseTool, ToolResult

class CalculatorTool(BaseTool):
    name = "calculator"
    description = "计算数学表达式"
    parameters_schema = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "数学表达式"}
        },
        "required": ["expression"]
    }

    async def execute(self, **kwargs) -> ToolResult:
        # 实现逻辑
        ...
```

### PromptSkill 示例

```yaml
id: code_assistant
name: 代码助手
description: 专业的编程助手
type: prompt
version: "1.0.0"
author: TARS
tags: [code, programming]
prompt_template: |
  你现在是一个专业的编程助手。请遵循以下原则：
  1. 代码质量：写出清晰、可维护的代码
  2. 格式规范：使用 markdown 代码块
  ...
parameters:
  - name: language
    type: string
    description: 编程语言偏好
    required: false
```

## 技能管理 API

```
GET    /api/skills/              # 列出所有技能
GET    /api/skills/{id}          # 技能详情
POST   /api/skills/create-prompt # 在线创建 PromptSkill
PUT    /api/skills/{id}/enable   # 启用
PUT    /api/skills/{id}/disable  # 禁用
DELETE /api/skills/{id}          # 卸载
POST   /api/skills/reload        # 重新加载
```

## 前端管理

在 Tools 页面的"已安装技能"Tab 中可以：
- 查看所有已安装技能（显示类型标签 Plugin/Prompt）
- 点击查看详情（含 Prompt 模板预览、参数列表）
- 启用/禁用技能
- 卸载技能
- 通过"添加技能"按钮在线创建 PromptSkill

## SkillHub 市场

从 GitHub 搜索和安装社区技能：

```
GET    /api/skillhub/search?q=xxx  # 搜索
POST   /api/skillhub/install       # 安装
POST   /api/skillhub/uninstall     # 卸载
GET    /api/skillhub/updates       # 检查更新
```

## 开发自定义技能

1. 在 `skills/` 下创建目录（目录名即技能 ID）
2. 编写 `skill.yaml`
3. 如果是 PluginSkill，编写 `main.py` 实现 `BaseTool`
4. 重启后端或调用 `/api/skills/reload`
