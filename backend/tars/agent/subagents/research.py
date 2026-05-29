# PortMeta Agent - Research SubAgent
# 研究子代理

from .base import SubAgent, SubAgentType
from typing import Dict, Any


class ResearchAgent(SubAgent):
    """研究子代理"""
    
    def __init__(self, llm_provider=None):
        super().__init__(SubAgentType.RESEARCH, llm_provider)
    
    def get_system_prompt(self) -> str:
        """获取研究助手的系统提示词"""
        return """你是一位专业的研究助手。
        
## 专业技能
- 擅长信息检索和整理
- 能够快速理解复杂主题
- 擅长综合分析和归纳总结
- 能够提供深入的研究报告

## 任务职责
1. 理解用户的研究需求
2. 搜索和收集相关信息
3. 整理和分析资料
4. 提供综合总结和建议
5. 引用可靠来源

## 研究原则
- 信息来源可靠
- 分析客观中立
- 内容全面准确
- 引用清晰标注

## 输出格式
- 提供结构化的研究结果
- 分点列出关键信息
- 给出结论和建议
- 如果有来源，提供引用说明"""
    
    async def execute(self, task: str, context: Dict[str, Any] = None) -> str:
        """
        执行研究任务

        Args:
            task: 研究任务描述
            context: 上下文信息（可选）

        Returns:
            str: 研究结果
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
            return f"研究任务处理中...\n任务: {task}\n提示词已准备好，等待LLM响应"
