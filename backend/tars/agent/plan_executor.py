"""PlanExecutor — 轻量计划-执行-验证状态机。

v5.0.5/A4: 不替代主循环，而是增强 prompt，让 Agent 在复杂任务时
自动生成执行计划，在每步完成后自我验证。

用法：
    plan_prompt = PlanExecutor.build_plan_prompt(user_content)
    → 注入到 system prompt 中，Agent 自动按计划执行
"""
from __future__ import annotations


PLAN_MODE_PROMPT = """
## 执行计划模式

你正在处理一个复杂任务。请按以下流程执行：

### 第一步：制定计划
在首次回复中，将任务分解为 3-7 个有序步骤。
使用格式：
```
📋 执行计划：
1. [步骤1描述] → 验证：确认XXX
2. [步骤2描述] → 验证：确认YYY
...
```

### 第二步：逐步执行
从第1步开始，每步执行后自我验证：
- ✅ 通过 → 继续下一步
- ❌ 失败 → 分析原因 → 修正方案或跳过 → 继续
每步完成后更新计划状态。

### 第三步：汇总报告
所有步骤完成或遇到无法解决的阻塞后，输出：
```
📊 执行报告：
- 已完成：X/总数
- 关键发现：[...]
- 阻塞项：[如有]
```

### 反模式警告
- 不要在未执行任何步骤时声称完成
- 不要跳过计划直接给结论
- 每步最多重试 2 次，超出则标记为阻塞并继续下一步
"""


class PlanExecutor:
    """判断是否需要计划模式，返回增强后的 prompt 片段。"""

    # 触发计划模式的关键词/模式
    PLAN_TRIGGERS = [
        "步骤", "依次", "然后", "接着", "最后",
        "先.*再", "分.*步", "逐步",
        "部署", "搭建", "迁移", "配置.*环境",
        "分析.*并.*写", "查.*然后.*生成",
        "同时.*还要", "包括.*和",
    ]

    @classmethod
    def should_use_plan(cls, user_content: str) -> bool:
        """判断用户消息是否适合启用计划模式。"""
        import re
        content = user_content.lower()
        score = 0
        for pattern in cls.PLAN_TRIGGERS:
            if re.search(pattern, content):
                score += 1
        # 消息长度 > 100 字且包含多个动作词
        if len(user_content) > 100:
            action_words = ["做", "写", "查", "改", "建", "部署", "测试", "运行", "分析", "生成"]
            action_count = sum(1 for w in action_words if w in content)
            if action_count >= 2:
                score += 2
        return score >= 2

    @classmethod
    def build_plan_prompt(cls, user_content: str) -> str:
        """返回计划模式的 prompt 注入。"""
        if not cls.should_use_plan(user_content):
            return ""
        return PLAN_MODE_PROMPT
