"""后处理反思 LLM — 每轮对话后异步更新 core memory + archive 长期记忆"""
import json
import re
from typing import List, Dict, Any, Optional

from .core_memory import CoreMemoryManager, BLOCK_NAMES
from .archival import ArchivalManager


REFLECTION_PROMPT = """你是记忆管理助手。基于本轮对话，判断需要做的记忆操作。

当前 core memory：
- persona: {persona}
- user_profile: {user_profile}
- project_context: {project_context}
- working_principles: {working_principles}

本轮对话（注意：{web_status}）：
User: {user_msg}
Assistant: {assistant_msg}

输出严格的 JSON 数组，每个元素是一个操作。不要任何额外文字。

操作类型：
- {{"op": "update_core", "block": "<persona|user_profile|project_context|working_principles>", "action": "append|replace", "old": "<被替换的旧文本>", "new": "<新文本>"}}
- {{"op": "archive", "content": "<简洁事实>", "category": "<fact|preference|decision|domain_knowledge>", "importance": <0.0-1.0>, "source": "<conversation|web>"}}
- {{"op": "noop"}}

规则：
- 用户明确反馈的协作准则 → working_principles
- 用户身份/技术栈/偏好 → user_profile
- 项目目标/进展变化 → project_context
- 风格反馈 → persona
- 一次性事实/对话片段 → archive
- 若使用了 web 搜索且学到领域知识 → archive 时 source="web"，category="domain_knowledge"
- 无明显新信息 → 输出 [{{"op": "noop"}}]

只输出 JSON 数组。"""


class Reflector:
    """反思器：每轮对话后异步触发，更新 core + archival"""

    def __init__(
        self,
        provider,
        core: CoreMemoryManager,
        archival: ArchivalManager,
    ):
        self.provider = provider
        self.core = core
        self.archival = archival

    async def reflect(
        self,
        user_msg: str,
        assistant_msg: str,
        used_web: bool = False,
    ) -> List[Dict[str, Any]]:
        """异步反思入口；返回执行的 ops 列表（用于日志）"""
        if not self.provider:
            return []
        if not user_msg.strip() or not assistant_msg.strip():
            return []

        snapshot = self.core.get_all()
        prompt = REFLECTION_PROMPT.format(
            persona=snapshot.get("persona", "")[:300],
            user_profile=snapshot.get("user_profile", "")[:300],
            project_context=snapshot.get("project_context", "")[:300],
            working_principles=snapshot.get("working_principles", "")[:300],
            user_msg=user_msg[:1500],
            assistant_msg=assistant_msg[:1500],
            web_status="本轮使用了 web 搜索" if used_web else "本轮未使用 web 搜索",
        )

        try:
            from ..models import ChatMessage
            messages = [
                ChatMessage(role="system", content="你是记忆管理助手。只输出 JSON。"),
                ChatMessage(role="user", content=prompt),
            ]
            response = await self.provider.chat(messages, stream=False, temperature=0.1)
            text = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            print(f"[Reflector] LLM 调用失败: {e}")
            return []

        ops = self._parse_ops(text)
        applied = []
        for op in ops:
            try:
                if await self._apply_op(op):
                    applied.append(op)
            except Exception as e:
                print(f"[Reflector] op 应用失败 {op}: {e}")
        return applied

    @staticmethod
    def _parse_ops(text: str) -> List[Dict[str, Any]]:
        text = text.strip()
        # 直接尝试
        try:
            data = json.loads(text)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            pass
        # ```json ... ```
        m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                pass
        # 找第一个 [...] 块
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                pass
        return []

    async def _apply_op(self, op: Dict[str, Any]) -> bool:
        kind = op.get("op")
        if kind == "noop":
            return False
        if kind == "update_core":
            block = op.get("block", "")
            if block not in BLOCK_NAMES:
                return False
            action = op.get("action", "append")
            new = op.get("new", "").strip()
            if not new:
                return False
            if action == "replace":
                old = op.get("old", "")
                return self.core.replace(block, old, new)
            return self.core.append(block, new)
        if kind == "archive":
            content = op.get("content", "").strip()
            if not content:
                return False
            category = op.get("category", "fact")
            importance = float(op.get("importance", 0.5))
            source = op.get("source", "conversation")
            mem = await self.archival.insert(
                content=content,
                category=category,
                importance=importance,
                source=source,
            )
            return mem is not None
        return False
