"""记忆管理器 V3 — 整合 Core + Archival + Reflector"""
from typing import Optional, List

from .core_memory import CoreMemoryManager, CoreMemoryAppendTool, CoreMemoryReplaceTool
from .archival import ArchivalManager
from .reflector import Reflector
from .search import HybridSearch
from .embeddings import EmbeddingProvider


class MemoryManager:
    """V3 记忆管理器：core memory + archival memory + reflector"""

    def __init__(
        self,
        db,
        provider=None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        self.db = db
        self.provider = provider
        self.embedding_provider = embedding_provider

        self.core = CoreMemoryManager(db)
        self.archival = ArchivalManager(db, embedding_provider)
        self.search = HybridSearch(db, embedding_provider)
        self.reflector = Reflector(provider, self.core, self.archival)

    def set_provider(self, provider):
        self.provider = provider
        self.reflector.provider = provider

    def get_context_for_query(self, query: str, limit: int = 5) -> str:
        """构建注入 system prompt 的记忆上下文：core memory + 检索到的 archival"""
        parts = []

        # Core memory（始终注入）
        core_render = self.core.render_for_prompt()
        if core_render.strip():
            parts.append(core_render)

        # Archival memory（语义+关键词检索）
        memories = self.search.search(query, limit)
        if memories:
            parts.append("\n## 相关长期记忆")
            for mem in memories:
                parts.append(f"- [{mem.category}] {mem.content}")

        return "\n".join(parts)

    async def reflect(self, user_msg: str, assistant_msg: str, used_web: bool = False):
        """每轮对话后由 Agent 异步调用"""
        return await self.reflector.reflect(user_msg, assistant_msg, used_web)

    async def add_manual_memory(self, content: str, category: str = "fact"):
        """手动添加（用于 API / 前端）"""
        return await self.archival.insert(content, category, importance=0.6, source="manual")

    def search_memories(self, query: str, limit: int = 5):
        return self.search.search(query, limit)

    def get_tools(self) -> List:
        """返回需要注册到 ToolRegistry 的工具列表"""
        return [
            CoreMemoryAppendTool(self.core),
            CoreMemoryReplaceTool(self.core),
        ]

    # 兼容老接口（main.py / agent.py 可能还在用）
    async def extract_and_save(self, conversation: str):
        """兼容老 API：旧的提取式接口现在是反思器的简化路径。
        conversation 格式："User: ...\nAssistant: ..." """
        if "\n" in conversation:
            user_part, _, assistant_part = conversation.partition("\n")
        else:
            user_part, assistant_part = conversation, ""
        user_msg = user_part.replace("User:", "").strip()
        assistant_msg = assistant_part.replace("Assistant:", "").strip()
        return await self.reflect(user_msg, assistant_msg)
