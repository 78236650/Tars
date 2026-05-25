"""记忆提取器 — LLM 驱动 + 启发式/正则 fallback"""
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

TURN_EXTRACTION_PROMPT = """你是技术知识整理助手。请从下面这轮对话中，提取适合写入知识库的技术要点。

重点关注 Assistant 回复中的：
- 问题根因、修复方案、配置步骤
- 架构/设计结论、约束与注意事项
- 命令、SQL、API、代码改动说明（用自然语言概括，不要整段复制代码）
- 可复用的经验、最佳实践、踩坑记录

也保留 User 明确表达的偏好、决策、项目背景（如有）。

输出 JSON 数组，每条包含：
- content: 一条独立、可检索的要点（20-200 字，中文为主）
- category: domain_knowledge / important_decision / project_record / user_preference / general

规则：
1. 技术解释类回复至少提取 1 条，最多 8 条
2. 不要把整段回复原样复制，拆成多条独立要点
3. 只输出 JSON 数组，不要 markdown 或其他文字

对话内容：
{conversation}"""


class LLMMemoryExtractor:
    """用 LLM 从对话中提取值得记住的信息"""

    async def extract(
        self,
        conversation: str,
        provider,
        *,
        prompt_template: str = EXTRACTION_PROMPT,
    ) -> List[Dict[str, Any]]:
        """调用 LLM 提取记忆；无 provider 时返回空列表，由上层走启发式 fallback。"""
        if not conversation.strip():
            return []

        if not provider:
            return []

        try:
            from ..models import ChatMessage

            messages = [
                ChatMessage(role="system", content="你是一个记忆提取助手。只输出 JSON，不要其他内容。"),
                ChatMessage(
                    role="user",
                    content=prompt_template.format(conversation=conversation[:6000]),
                ),
            ]
            response = await provider.chat(messages, stream=False, temperature=0.1)

            text = response.content if hasattr(response, "content") else str(response)
            return self._parse_response(text)
        except Exception as e:
            print(f"[MemoryExtractor] LLM 提取失败: {e}")
            return []

    def _parse_response(self, text: str) -> List[Dict[str, Any]]:
        """解析 LLM 返回的 JSON"""
        text = text.strip()

        try:
            result = json.loads(text)
            if isinstance(result, list):
                return [m for m in result if isinstance(m, dict) and "content" in m]
            return []
        except json.JSONDecodeError:
            pass

        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1))
                if isinstance(result, list):
                    return [m for m in result if isinstance(m, dict) and "content" in m]
            except json.JSONDecodeError:
                pass

        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
                if isinstance(result, list):
                    return [m for m in result if isinstance(m, dict) and "content" in m]
            except json.JSONDecodeError:
                pass

        return []


class HeuristicTurnExtractor:
    """从助手技术回复中启发式提取要点（LLM 不可用或返回空时使用）。"""

    MAX_ITEMS = 8
    MIN_LEN = 12

    CATEGORY_MAP = {
        "domain_knowledge": "domain_knowledge",
        "important_decision": "decision",
        "project_record": "fact",
        "user_preference": "preference",
        "general": "fact",
        "decision": "decision",
        "preference": "preference",
        "fact": "fact",
    }

    def extract(self, user_msg: str, assistant_msg: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set[str] = set()
        body = self._strip_code_blocks(assistant_msg or "")

        def add(content: str, category: str = "domain_knowledge") -> None:
            cleaned = re.sub(r"\s+", " ", content.strip())
            cleaned = re.sub(r"^[\-*•\d.)]+\s*", "", cleaned)
            cleaned = cleaned.strip("*_ ")
            if len(cleaned) < self.MIN_LEN:
                return
            key = cleaned.lower()[:160]
            if key in seen:
                return
            seen.add(key)
            items.append(
                {
                    "content": cleaned[:500],
                    "category": self.CATEGORY_MAP.get(category, "domain_knowledge"),
                }
            )

        for match in re.finditer(r"^#{1,4}\s+(.+)$", body, re.MULTILINE):
            add(match.group(1).strip(), "domain_knowledge")

        for match in re.finditer(r"^[\-*•]\s+(.+)$", body, re.MULTILINE):
            add(match.group(1).strip(), "domain_knowledge")

        for match in re.finditer(r"^\d+[\.)]\s+(.+)$", body, re.MULTILINE):
            add(match.group(1).strip(), "domain_knowledge")

        for match in re.finditer(r"\*\*(.+?)\*\*", body):
            add(match.group(1).strip(), "domain_knowledge")

        if not items:
            for para in re.split(r"\n\s*\n", body):
                para = para.strip()
                if len(para) >= 30:
                    add(para[:400], "domain_knowledge")
                if len(items) >= self.MAX_ITEMS:
                    break

        if not items and len(body.strip()) >= 30:
            add(body.strip()[:600], "domain_knowledge")

        user_msg = (user_msg or "").strip()
        if user_msg and len(items) < self.MAX_ITEMS:
            add(f"背景问题：{user_msg[:180]}", "fact")

        return items[: self.MAX_ITEMS]

    @staticmethod
    def _strip_code_blocks(text: str) -> str:
        without_fence = re.sub(r"```[\s\S]*?```", "\n", text)
        return re.sub(r"`([^`]+)`", r"\1", without_fence)


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
