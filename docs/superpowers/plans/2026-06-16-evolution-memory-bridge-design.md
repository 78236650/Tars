# Evolution ↔ Memory 打通设计方案

> 创建：2026-06-16 · 对应评估结论：两条核心线零引用是最大架构短板

## 问题

- Evolution 有 FeedbackCollector / ResponseEvaluator / CaseDistiller / Orchestrator，但**从不读 Memory**
- Memory 有 solution / procedure / correction / episodic，但**从不被 Evolution 分析**
- 用户纠正 TARS → Memory 存了 → Evolution 不知道 → 下次还犯

## 目标

| 闭环 | 路径 | 效果 |
|------|------|------|
| **修正闭环** | 用户纠正 → Reflector log_correction → Evolution 分析模式 → 自动调整行为 | 同样的错不犯第二次 |
| **经验复用** | 用户成功方案 → log_solution → Evolution 发现高频模式 → 主动推荐 | "你之前用方案A解决过类似问题" |
| **能力进化** | Memory 数据 → Evolution 分析 → 调整 prompt/权重 | Agent 越用越聪明 |

## 架构

```
┌──────────────────┐     ┌──────────────────────┐
│   Memory System  │     │   Evolution System   │
│                  │     │                      │
│  Reflector       │     │  Orchestrator        │
│  └─ log_correction│←──│  └─ analyze_memory()  │ ← 新增入口
│                  │     │                      │
│  MemoryManager   │     │  MemoryAwareAnalyzer │ ← 新增组件
│  └─ get_solutions│────→│  └─ cluster/pattern  │
│  └─ get_episodes │────→│  └─ time_series      │
│                  │     │                      │
│  HybridSearch    │     │  ApplyEngine         │
│                  │     │  └─ inject_rule()    │ ← 写回 Memory/Config
└──────────────────┘     └──────────────────────┘
```

## 实施：三个组件

### 1. Reflector 新增 `log_correction` op（修正闭环入口）

当用户说"不对/错了/应该是/改一下"等纠正性语句，Reflector 产出：

```json
{"op": "log_correction",
 "what_was_wrong": "TARS 回答了 X",
 "what_is_correct": "正确答案是 Y",
 "category": "fact_error|misunderstanding|wrong_approach|outdated",
 "importance": 0.85}
```

存入 `category="correction"`, `memory_type="procedural"`。

### 2. MemoryAwareAnalyzer（分析桥梁）

EvolutionOrchestrator.optimize() 中新增步骤：

```python
def optimize(self, tenant_id):
    # ... 现有逻辑 ...
    
    # 新增：从 Memory 分析模式
    patterns = self.memory_analyzer.analyze(tenant_id)
    
    # 如果发现可操作的改进，写入
    if patterns.avoidance_rules:
        self.apply_engine.apply_avoidance_rules(patterns.avoidance_rules)
    if patterns.recommendations:
        self.apply_engine.apply_recommendations(patterns.recommendations)
```

分析器逻辑：
- 拉取 correction 类记忆 → 按 what_was_wrong 聚类 → 生成 avoidance_rules
- 拉取 solution 类记忆 → 按 entity 聚类 → 发现高频解决模式
- 写入 core_memory working_principles（"不要再做X"）
- 更新 proactive_reminders 配置

### 3. MemoryFeedbackBridge（双向写入）

```python
class MemoryFeedbackBridge:
    """Evolution → Memory 写入桥梁"""
    
    def record_avoidance_rule(self, tenant_id, rule, source_corrections):
        """将 Evolution 发现的避免规则写入 working_principles"""
        ...
    
    def record_solution_pattern(self, tenant_id, pattern, source_solutions):
        """将高频解决方案模式提升为 pinned memory"""
        ...
```

## 实施顺序

| 步骤 | 内容 | 改动量 |
|------|------|--------|
| Step 1 | Reflector 新增 log_correction op | ~40行 |
| Step 2 | MemoryAwareAnalyzer 实现 | ~80行 |
| Step 3 | MemoryFeedbackBridge 实现 | ~50行 |
| Step 4 | EvolutionOrchestrator 集成调用 | ~15行 |
| Step 5 | 测试验证 | - |

---

*设计日期：2026-06-16*
