"""Archival Memory — 长期记忆管理（写入 + 去重 + 强化）"""
from typing import Optional

from .deduplicator import MemoryDeduplicator
from .embeddings import EmbeddingProvider, serialize_vector
from ..org import ORG_ID
from ..vectorstore.scope import memory_chroma_metadata


class ArchivalManager:
    """长期记忆写入器"""

    def __init__(
        self,
        db,
        embedding_provider: Optional[EmbeddingProvider] = None,
        tenant_id: str = ORG_ID,
        vector_store=None,
    ):
        self.db = db
        self.embedding_provider = embedding_provider
        self.deduplicator = MemoryDeduplicator(embedding_provider)
        self.tenant_id = tenant_id
        self.vector_store = vector_store

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

        existing = self.db.get_recent_memories(50, tenant_id=self.tenant_id)
        is_dup, update_target = self.deduplicator.is_duplicate(content, existing)

        if is_dup and not update_target:
            return None

        if is_dup and update_target:
            self.db.update_memory(update_target.id, content=content, tenant_id=self.tenant_id)
            # 同步更新 Chroma
            if self.vector_store and self.vector_store.is_available:
                try:
                    scope = getattr(update_target, "scope", "private") or "private"
                    uid = getattr(update_target, "user_id", None)
                    self.vector_store.delete(
                        ids=[update_target.id],
                        tenant_id=self.tenant_id,
                        collection_name="memories",
                    )
                    self.vector_store.add_documents(
                        documents=[content],
                        metadatas=[
                            memory_chroma_metadata(
                                scope, uid, category=category, importance=importance, source=source
                            )
                        ],
                        ids=[update_target.id],
                        tenant_id=self.tenant_id,
                        collection_name="memories",
                    )
                except Exception as e:
                    print(f"[ArchivalManager] Chroma update failed: {e}")
            return update_target

        embedding_blob = None
        embedding_vec = None
        if self.embedding_provider:
            try:
                embedding_vec = self.embedding_provider.encode([content])[0]
                embedding_blob = serialize_vector(embedding_vec)
            except Exception as e:
                print(f"[ArchivalManager] 嵌入生成失败: {e}")

        mem = self.db.add_memory(
            content=content,
            category=category,
            importance=importance,
            embedding=embedding_blob,
            source=source,
            tenant_id=self.tenant_id,
        )

        # 同步写入 Chroma 向量数据库
        if mem and self.vector_store and self.vector_store.is_available:
            try:
                self.vector_store.add_documents(
                    documents=[content],
                    metadatas=[
                        memory_chroma_metadata(
                            mem.scope,
                            mem.user_id,
                            category=category,
                            importance=importance,
                            source=source,
                        )
                    ],
                    ids=[mem.id],
                    tenant_id=self.tenant_id,
                    collection_name="memories",
                )
            except Exception as e:
                print(f"[ArchivalManager] Chroma insert failed: {e}")

        return mem

    def reinforce(self, memory_id: str):
        self.db.reinforce_memory(memory_id, tenant_id=self.tenant_id)
