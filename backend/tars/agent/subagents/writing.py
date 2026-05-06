# TARS Agent - Writing SubAgent
# 写作子代理

from .base import SubAgent, SubAgentType
from typing import Dict, Any


class WritingAgent(SubAgent):
    """写作子代理"""
    
    def __init__(self, llm_provider=None):
        super().__init__(SubAgentType.WRITING, llm_provider)
    
    def get_system_prompt(self) -> str:
        """获取写作助手的系统提示词"""
        return """你是一位专业的写作助手。
        
## 专业技能
- 擅长各种文体写作：文章、报告、邮件、文案、故事等
- 精通中文和英文写作
- 能够根据不同目的调整语气和风格
- 擅长创意写作和内容创作

## 任务职责
1. 理解用户的写作需求和目标
2. 创作高质量的文本内容
3. 提供润色和编辑建议
4. 帮助优化表达和结构

## 写作原则
- 语言流畅自然
- 逻辑清晰有条理
- 内容丰富有深度
- 风格符合目标受众

## 输出格式
- 根据需求提供完整的文本内容
- 如果是长文，提供清晰的结构和分段
- 必要时提供多种版本供选择"""
    
    async def execute(self, task: str, context: Dict[str, Any] = None) -> str:
        """
        执行写作任务

        Args:
            task: 写作任务描述
            context: 上下文信息（可选）

        Returns:
            str: 写作结果
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
            return f"写作任务处理中...\n任务: {task}\n提示词已准备好，等待LLM响应"
