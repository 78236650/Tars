# Portmeta Agent - Code SubAgent
# 代码子代理

from .base import SubAgent, SubAgentType
from typing import Dict, Any


class CodeAgent(SubAgent):
    """代码编写子代理"""

    def __init__(self, llm_provider=None):
        super().__init__(SubAgentType.CODE, llm_provider)

    def get_system_prompt(self) -> str:
        """获取代码助手的系统提示词"""
        return """你是一位专业的代码工程师助手。

## 专业技能
- 精通多种编程语言：Python、JavaScript、TypeScript、Go、Rust、Java等
- 熟悉各种开发框架和工具
- 能够编写高质量、可维护的代码
- 擅长代码优化和调试

## 任务职责
1. 分析用户的代码需求
2. 编写清晰、高效、有注释的代码
3. 提供代码解释和使用说明
4. 帮助调试和修复代码问题

## 输出格式
- 代码使用代码块包裹
- 提供必要的注释
- 说明代码的功能和使用方法
- 如果有多种实现方案，给出对比和建议"""

    async def execute(self, task: str, context: Dict[str, Any] = None) -> str:
        """
        执行代码相关任务

        Args:
            task: 代码任务描述
            context: 上下文信息（可选）

        Returns:
            str: 代码执行结果或代码输出
        """
        from ...models.base import ChatMessage
        prompt = self.merge_with_personality(context.get('personality') if context else None)

        if self.llm_provider:
            messages = [
                ChatMessage(role="system", content=prompt),
                ChatMessage(role="user", content=task)
            ]
            response = await self.llm_provider.chat(messages, stream=False)
            return response.content if hasattr(response, 'content') else str(response)
        else:
            return f"代码任务处理中...\n任务: {task}\n提示词已准备好，等待LLM响应"
