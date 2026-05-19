"""记忆提取器 — LLM 驱动 + 正则 fallback"""
import json
import re
from typing import Any, Dict, List, Optional


EXTRACTION_PROMPT = """从以下对话中提取值得长期记住的信息。只提取明确表达的事实，不要推测。

输出 JSON 数组，每条记忆包含：
- content: 简洁的事实描述（一句话）
- category: user_preference / important_decision / project_record / general

只输出 JSON 数组，不要其他内容。如果没有值得记住的信息，输出空数组 []。

对话内容：
{conversation}"""


class LLMMemoryExtractor:
    """用 LLM 从对话中提取值得记住的信息"""

    async def extract(self, conversation: str, provider) -> List[Dict[str, Any]]:
        """调用 LLM 提取记忆，失败或无 provider 时 fallback 到正则"""
        if not conversation.strip():
            return []

        if not provider:
            return RegexExtractor().extract(conversation)

        try:
            from ..models import ChatMessage
            messages = [
                ChatMessage(role="system", content="你是一个记忆提取助手。只输出 JSON，不要其他内容。"),
                ChatMessage(role="user", content=EXTRACTION_PROMPT.format(conversation=conversation[:3000])),
            ]
            response = await provider.chat(messages, stream=False, temperature=0.1)

            text = response.content if hasattr(response, "content") else str(response)
            parsed = self._parse_response(text)
            if parsed:
                return parsed
            return RegexExtractor().extract(conversation)
        except Exception as e:
            print(f"[MemoryExtractor] LLM 提取失败，fallback 到正则: {e}")
            return RegexExtractor().extract(conversation)

    def _parse_response(self, text: str) -> List[Dict[str, Any]]:
        """解析 LLM 返回的 JSON"""
        text = text.strip()

        # 尝试直接解析
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return [m for m in result if isinstance(m, dict) and "content" in m]
            return []
        except json.JSONDecodeError:
            pass

        # 尝试从 ```json ... ``` 中提取
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1))
                if isinstance(result, list):
                    return [m for m in result if isinstance(m, dict) and "content" in m]
            except json.JSONDecodeError:
                pass

        # 尝试找到 [ ... ] 块
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
                if isinstance(result, list):
                    return [m for m in result if isinstance(m, dict) and "content" in m]
            except json.JSONDecodeError:
                pass

        return []


class RegexExtractor:
    """修复后的正则提取器（fallback）"""

    PATTERNS = {
        "user_preference": [
            r"我喜欢([^。\n！？]+)",
            r"我偏好([^。\n！？]+)",
            r"我通常([^。\n！？]+)",
            r"我习惯([^。\n！？]+)",
            r"不要([^。\n！？]+)",
            r"I prefer ([^.\n!?]+)",
            r"I like ([^.\n!?]+)",
            r"I usually ([^.\n!?]+)",
        ],
        "important_decision": [
            r"决定([^。\n！？]+)",
            r"选择([^。\n！？]+)作为",
            r"采用([^。\n！？]+)",
            r"We decided ([^.\n!?]+)",
            r"We chose ([^.\n!?]+)",
        ],
        "project_record": [
            r"完成了([^。\n！？]+)",
            r"启动了([^。\n！？]+)",
            r"使用了([^。\n！？]+)",
            r"部署了([^。\n！？]+)",
            r"Completed ([^.\n!?]+)",
            r"Deployed ([^.\n!?]+)",
        ],
    }

    def extract(self, text: str) -> List[Dict[str, Any]]:
        memories = []
        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text):
                    content = match.group(0).strip()
                    if len(content) > 5:
                        memories.append({"content": content, "category": category})
        return memories
