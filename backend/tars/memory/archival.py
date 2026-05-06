"""Archival Memory — 长期记忆管理（写入 + 去重 + 强化）"""
from typing import Optional

from .deduplicator import MemoryDeduplicator
from .embeddings import EmbeddingProvider, serialize_vector


class ArchivalManager:
    """长期记忆写入器"""

    def __init__(self, db, embedding_provider: Optional[EmbeddingProvider] = None):
        self.db = db
        self.embedding_provider = embedding_provider
        self.deduplicator = MemoryDeduplicator(embedding_provider)

    async def insert(
        self,
        content: str,
        category: str = "fact",
        importance: float = 0.5,
        source: str = "conversation",
    ):
        """写入新记忆。重复 → 返回 None；包含 → 更新旧记忆并返回更新后的对象"""
        content = content.strip()
        if not content or len(content) < 5:
            return None

        existing = self.db.get_recent_memories(50)
        is_dup, update_target = self.deduplicator.is_duplicate(content, existing)

        if is_dup and not update_target:
            return None

        if is_dup and update_target:
            self.db.update_memory(update_target.id, content=content)
            return update_target

        embedding_blob = None
        if self.embedding_provider:
            try:
                vec = self.embedding_provider.encode([content])[0]
                embedding_blob = serialize_vector(vec)
            except Exception as e:
                print(f"[ArchivalManager] 嵌入生成失败: {e}")

        return self.db.add_memory(
            content=content,
            category=category,
            importance=importance,
            embedding=embedding_blob,
            source=source,
        )

    def reinforce(self, memory_id: str):
        self.db.reinforce_memory(memory_id)
