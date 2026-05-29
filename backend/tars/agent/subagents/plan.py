# Portmeta Agent - Plan SubAgent
# 规划子代理

from .base import SubAgent, SubAgentType
from typing import Dict, Any


class PlanAgent(SubAgent):
    """规划子代理"""
    
    def __init__(self, llm_provider=None):
        super().__init__(SubAgentType.PLAN, llm_provider)
    
    def get_system_prompt(self) -> str:
        """获取规划助手的系统提示词"""
        return """你是一位专业的规划和组织助手。
        
## 专业技能
- 擅长制定计划和目标
- 能够分解复杂任务
- 擅长时间管理和优先级排序
- 能够创建可行的执行方案

## 任务职责
1. 理解用户的目标和需求
2. 制定详细的行动计划
3. 分解任务和步骤
4. 设定时间节点和里程碑
5. 提供执行建议

## 规划原则
- 目标明确具体
- 步骤清晰可行
- 时间安排合理
- 考虑潜在风险

## 输出格式
- 使用结构化列表展示计划
- 分阶段列出任务步骤
- 设定时间节点
- 提供执行建议和注意事项"""
    
    async def execute(self, task: str, context: Dict[str, Any] = None) -> str:
        """
        执行规划任务

        Args:
            task: 规划任务描述
            context: 上下文信息（可选）

        Returns:
            str: 规划结果
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
            return f"规划任务处理中...\n任务: {task}\n提示词已准备好，等待LLM响应"
