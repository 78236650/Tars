# TARS 自进化系统使用文档

> **能力基线：v4.2.0 Phase 2**（Evolution 闭环）· **当前平台：v4.3.2** — 见 [VERSION.md](docs/01-项目概览/VERSION.md)

## Phase 2 架构（v4.2.0）

| 组件 | 职责 |
|------|------|
| **FeedbackCollector** | 统一 A/B/C/D 反馈入 `evolution_events` |
| **EvolutionOrchestrator** | 窗口聚合、触发 optimize、EvalRunner 门禁 |
| **ApplyEngine** | 唯一写回入口（SOUL.md / prompts），audit + rollback |
| **EvalRunner** | `tests/evolution/eval_set.yaml`（≥20 场景） |

写回目标：`~/.tars/workspaces/{tenant_id}/SOUL.md` 与 `prompts/*.md`。每次写回记录于 `evolution_apply_log`，eval 退步 >5% 自动 rollback。

### 接线点（v4.2.0 Phase 2 完成）

| 来源 | 位置 |
|------|------|
| Agent 回合结束 | `AgentV2.handle_message` → `EvolutionManager.ingest_turn` |
| 工具成败 | `ToolDispatcher.execute_tool` → `FeedbackCollector.record_tool_result` |
| Chat 👎 WS | WebSocket `message_feedback` 事件 |
| Chat/API 反馈 | `POST /api/evolution/feedback` |
| Insight 👎 | `AdoptionService.process_feedback` |
| 技能调用 | `SkillCurator.record_call(skill_id, success=…)`（Agent on_tool_result） |

---

> **历史版本：v2.0.0**（自进化 API 接口保持兼容）

## 概述

TARS 自进化系统是一个智能学习和优化模块，能够根据用户反馈自动优化 Agent 的人格参数、子代理配置和提示词。通过持续学习用户交互模式，TARS 可以不断提升响应质量和用户体验。

## 核心功能

| 功能 | 说明 |
|------|------|
| **效果评估** | 自动评估对话质量（相关性、完整性、准确性等） |
| **人格优化** | 根据反馈自动调整人格参数 |
| **子代理优化** | 优化任务委派策略和人格融合权重 |
| **提示词调优** | 自动优化系统提示词 |
| **反馈收集** | 支持显式和隐式反馈 |

---

## 触发方式

### 1. **自动触发**（推荐）

系统默认启用自动优化模式，每 **50 次对话** 自动触发一次优化。

```python
# 默认配置
evolution_manager.auto_optimize = True  # 启用自动优化
evolution_manager.optimize_interval = 50  # 每50次对话优化一次
```

### 2. **手动触发**

通过 API 或代码手动触发优化：

```python
# 代码方式
from tars.evolution import EvolutionManager

manager = EvolutionManager()
results = manager.optimize()
print(results)
```

```bash
# API 方式
curl -X POST http://localhost:8000/api/evolution/optimize
```

### 3. **定时触发**

可以通过定时任务定期触发优化：

```python
import asyncio
from tars.evolution import EvolutionManager

async def scheduled_optimization():
    manager = EvolutionManager()
    while True:
        manager.optimize()
        await asyncio.sleep(3600)  # 每小时优化一次
```

---

## API 接口使用

### 1. 获取统计信息

```bash
GET /api/evolution/stats
```

**响应示例：**
```json
{
  "success": true,
  "message": "success",
  "data": {
    "total": 150,
    "with_evaluation": 145,
    "avg_score": 0.78,
    "score_trend": "improving",
    "enabled": true,
    "auto_optimize": true,
    "conversation_count": 150,
    "subagent_recommendations": {...},
    "prompt_history": {...}
  }
}
```

### 2. 获取优化建议

```bash
GET /api/evolution/suggestions
```

**响应示例：**
```json
{
  "success": true,
  "message": "success",
  "data": {
    "personality": {
      "humor": 0.85,
      "creativity": 0.72
    }
  }
}
```

### 3. 手动触发优化

```bash
POST /api/evolution/optimize
```

**响应示例：**
```json
{
  "success": true,
  "message": "优化完成",
  "data": {
    "timestamp": "2026-05-05T10:30:00",
    "personality_optimized": true,
    "subagent_optimized": true,
    "prompts_tuned": true,
    "new_personality": {...},
    "subagent_weights": {...}
  }
}
```

### 4. 提交对话反馈

```bash
POST /api/evolution/feedback
Content-Type: application/json

{
  "conversation_id": "conv_001",
  "query": "帮我写一个 Python 函数",
  "response": "好的，我来帮你写...",
  "feedback": "非常好！",
  "context": {
    "tools_used": ["terminal"],
    "subagent_used": "code",
    "prompt_type": "master"
  }
}
```

**响应示例：**
```json
{
  "success": true,
  "message": "反馈已记录",
  "data": {
    "overall_score": 0.85,
    "relevance": 0.92,
    "completeness": 0.88,
    "accuracy": 0.85,
    "style_match": 0.80
  }
}
```

### 5. 更新自进化设置

```bash
PUT /api/evolution/settings
Content-Type: application/json

{
  "enabled": true,
  "auto_optimize": false
}
```

**响应示例：**
```json
{
  "success": true,
  "message": "设置已更新",
  "data": {
    "enabled": true,
    "auto_optimize": false
  }
}
```

---

## 代码使用示例

### 示例 1：基本使用

```python
from tars.evolution import EvolutionManager

# 初始化管理器
manager = EvolutionManager()

# 记录对话（自动评估）
evaluation = manager.record_conversation(
    conversation_id="conv_001",
    query="帮我写一个 Python 函数",
    response="好的，我来帮你写...",
    context={
        "tools_used": [],
        "subagent_used": None
    }
)

print(f"评估分数: {evaluation.overall_score}")

# 手动触发优化
results = manager.optimize()
print(f"优化结果: {results}")
```

### 示例 2：带显式反馈

```python
from tars.evolution import EvolutionManager

manager = EvolutionManager()

# 用户给出明确反馈
evaluation = manager.record_conversation(
    conversation_id="conv_002",
    query="解释量子计算",
    response="量子计算是...",
    explicit_feedback="太棒了！10/10",  # 用户显式评分
    context={
        "prompt_type": "master"
    }
)

print(f"显式反馈评分: {evaluation.overall_score}")
```

### 示例 3：批量导入历史对话

```python
from tars.evolution import EvolutionManager

manager = EvolutionManager()

# 批量导入历史对话
historical_conversations = [
    {"query": "问题1", "response": "回答1", "feedback": "好"},
    {"query": "问题2", "response": "回答2", "feedback": "很好"},
    # ... 更多对话
]

for i, conv in enumerate(historical_conversations):
    manager.record_conversation(
        conversation_id=f"history_{i}",
        query=conv["query"],
        response=conv["response"],
        explicit_feedback=conv.get("feedback")
    )

# 触发优化
manager.optimize()
```

---

## 配置说明

### 配置项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | bool | True | 是否启用自进化 |
| `auto_optimize` | bool | True | 是否自动优化 |
| `optimize_interval` | int | 50 | 自动优化间隔（对话数） |
| `learning_rate` | float | 0.05 | 优化学习率 |
| `exploration_rate` | float | 0.2 | 探索率（尝试新配置的概率） |

### 修改配置

```python
from tars.evolution import EvolutionManager

manager = EvolutionManager()

# 修改配置
manager.enabled = True
manager.auto_optimize = True
manager._optimize_interval = 100  # 每100次对话优化

# 配置会自动持久化到 ~/.tars/evolution/state.json
```

### 配置文件位置

配置文件存储在：
```
~/.tars/evolution/state.json
```

```json
{
  "enabled": true,
  "auto_optimize": true,
  "optimize_interval": 50,
  "conversation_count": 150
}
```

---

## 评估维度说明

### 评分指标（0-1 分数）

| 指标 | 说明 | 权重 |
|------|------|------|
| **overall_score** | 综合评分 | - |
| **relevance** | 响应与问题的相关性 | 30% |
| **completeness** | 回答的完整性 | 25% |
| **accuracy** | 内容准确性 | 25% |
| **style_match** | 风格与人格匹配度 | 10% |
| **tool_efficiency** | 工具使用效率 | 10% |

### 隐式反馈检测

系统会自动检测以下隐式信号：
- **追问模式**：用户是否连续追问（表示可能回答不完整）
- **响应长度**：过短或过长的响应可能影响质量
- **代码块存在**：技术问题应该包含代码示例
- **关键词分析**：正向/负向关键词检测

---

## 工作流程图

```
┌─────────────────────────────────────────────────────────────┐
│                     用户对话流程                            │
├─────────────────────────────────────────────────────────────┤
│                                                           │
│  用户输入 → 生成响应 → 记录对话 → 自动评估                    │
│                                      │                     │
│                                      ▼                     │
│                              累计对话数 >= 50?              │
│                                     │                      │
│                    ┌─────────────────┴─────────────────┐    │
│                    │ YES                              │ NO │
│                    ▼                                  │    │
│          ┌─────────────────┐                         │    │
│          │   触发优化流程   │◄────────────────────────┘    │
│          └────────┬────────┘                              │
│                   │                                       │
│          ┌────────┴────────┐                             │
│          │ 人格参数优化    │                             │
│          │ 子代理配置优化  │                             │
│          │ 提示词调优      │                             │
│          └────────┬────────┘                             │
│                   │                                       │
│                   ▼                                       │
│          ┌─────────────────┐                             │
│          │ 更新 Agent 配置  │                             │
│          └─────────────────┘                             │
│                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 最佳实践

### 1. 生产环境建议

```python
# 生产环境配置
manager = EvolutionManager()
manager.auto_optimize = True
manager._optimize_interval = 100  # 增加优化间隔
```

### 2. 监控和调试

```python
# 获取详细统计
stats = manager.get_stats()
print(f"平均分数: {stats['avg_score']}")
print(f"趋势: {stats['score_trend']}")
print(f"对话数: {stats['conversation_count']}")

# 获取人格优化建议
suggestions = manager.get_personality_suggestions()
print(f"建议调整的参数: {suggestions}")
```

### 3. 集成到 WebSocket 对话

```python
# 在 WebSocket 消息处理中集成
async def handle_message(message):
    # 处理用户消息...
    response = await agent.generate_response(message)
    
    # 记录对话用于自进化
    manager.record_conversation(
        conversation_id=message.get('conversation_id'),
        query=message.get('content'),
        response=response,
        context={
            "tools_used": [],
            "subagent_used": None
        }
    )
    
    return response
```

---

## 注意事项

1. **数据量要求**：优化需要至少 20 条对话记录才能产生有意义的结果
2. **优化时机**：建议在低峰期手动触发大规模优化
3. **配置备份**：定期备份 `~/.tars/evolution/` 目录
4. **性能影响**：优化过程会消耗一定资源，建议控制频率

---

## 故障排除

### 问题：优化未触发

**原因**：对话数未达到优化间隔

**解决**：
```python
# 检查对话数
stats = manager.get_stats()
print(f"对话数: {stats['conversation_count']}")

# 手动触发
manager.optimize()
```

### 问题：评分异常

**原因**：缺乏足够的上下文信息

**解决**：
```python
# 确保提供完整的上下文
manager.record_conversation(
    conversation_id="test",
    query="问题",
    response="回答",
    context={
        "tools_used": [],
        "subagent_used": "code",
        "prompt_type": "master"
    }
)
```

---

## 相关文件

| 文件 | 说明 |
|------|------|
| `tars/evolution/manager.py` | 自进化管理器核心 |
| `tars/evolution/evaluator.py` | 效果评估器 |
| `tars/evolution/optimizer.py` | 参数优化器 |
| `tars/evolution/prompt_tuner.py` | 提示词调优器 |
| `tars/main.py` | API 接口定义 |

---

## 版本历史

| 版本 | 说明 |
|------|------|
| v1.0 | 初始版本，包含基本的评估和优化功能 |

---

---

*平台文档对齐: TARS v4.3.2 · 见 [VERSION.md](docs/01-项目概览/VERSION.md) · 更新: 2026-05-26*
