# TARS Agent - Data SubAgent
# 数据分析子代理

from .base import SubAgent, SubAgentType
from typing import Dict, Any


class DataAgent(SubAgent):
    """数据分析子代理"""
    
    def __init__(self, llm_provider=None):
        super().__init__(SubAgentType.DATA, llm_provider)
    
    def get_system_prompt(self) -> str:
        """获取数据分析助手的系统提示词"""
        return """你是一位专业的数据分析助手。
        
## 专业技能
- 精通数据分析方法和技术
- 熟悉数据可视化工具和技术
- 能够解读复杂数据并提取洞察
- 擅长制作数据报告和图表

## 任务职责
1. 分析用户的数据需求
2. 处理和清洗数据
3. 进行统计分析和建模
4. 生成数据可视化建议
5. 撰写数据分析报告

## 分析原则
- 数据准确可靠
- 分析方法科学严谨
- 结论清晰明确
- 建议切实可行

## 输出格式
- 提供数据解读和分析结果
- 如果需要图表，描述图表类型和内容
- 给出关键洞察和建议
- 保持专业但易懂的表达"""
    
    async def execute(self, task: str, context: Dict[str, Any] = None) -> str:
        """
        执行数据分析任务

        Args:
            task: 数据分析任务描述
            context: 上下文信息（可选）

        Returns:
            str: 分析结果
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
            return f"数据分析任务处理中...\n任务: {task}\n提示词已准备好，等待LLM响应"
