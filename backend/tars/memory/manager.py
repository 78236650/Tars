"""记忆管理器 V3 — 整合 Core + Archival + Reflector"""
from typing import Optional, List

from .core_memory import CoreMemoryManager, CoreMemoryAppendTool, CoreMemoryReplaceTool
from .archival import ArchivalManager
from .reflector import Reflector
from .search import HybridSearch
from .embeddings import EmbeddingProvider
from .compressor import MemoryCompressor


class MemoryManager:
    """V3 记忆管理器：core memory + archival memory + reflector"""

    def __init__(
        self,
        db,
        provider=None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        tenant_id: str = "default",
        vector_store=None,
    ):
        self.db = db
        self.provider = provider
        self.embedding_provider = embedding_provider
        self.tenant_id = tenant_id
        self.vector_store = vector_store

        self.core = CoreMemoryManager(db, tenant_id=tenant_id)
        self.archival = ArchivalManager(db, embedding_provider, tenant_id=tenant_id, vector_store=vector_store)
        self.search = HybridSearch(db, embedding_provider, tenant_id=tenant_id, vector_store=vector_store)
        self.reflector = Reflector(provider, self.core, self.archival, db=db)
        self.compressor = MemoryCompressor(db, provider=provider, tenant_id=tenant_id)
        self.reflector.tenant_id = tenant_id

    def set_provider(self, provider):
        self.provider = provider
        self.reflector.provider = provider
        self.compressor.provider = provider

    def set_tenant(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.core.tenant_id = tenant_id
        self.archival.tenant_id = tenant_id
        self.search.tenant_id = tenant_id
        self.reflector.tenant_id = tenant_id
        self.compressor.tenant_id = tenant_id
        return self

    def for_tenant(self, tenant_id: str):
        scoped = MemoryManager(
            db=self.db,
            provider=self.provider,
            embedding_provider=self.embedding_provider,
            tenant_id=tenant_id,
            vector_store=self.vector_store,
        )
        return scoped

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

    def cleanup(self) -> dict:
        """执行遗忘清理：衰减 + 删除过期记忆。返回清理统计。"""
        decayed = self.db.decay_importance()
        deleted = self.db.cleanup_old_memories()
        return {"decayed": decayed, "deleted": deleted}

    def start_migration_worker(self):
        """启动后台热回填 worker（低优先级，每 30s 取 10 条旧记忆回填 entity_refs）"""
        import asyncio
        import threading

        async def _worker():
            while True:
                try:
                    conn = self.db._get_conn()
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT id, content, created_at FROM memories WHERE entity_refs IS NULL LIMIT 10"
                    )
                    rows = cur.fetchall()
                    for row in rows:
                        # 简易回填：用创建时间作为 event_time
                        cur.execute(
                            "UPDATE memories SET event_time=?, entity_refs='[]' WHERE id=?",
                            (row[2], row[0]),
                        )
                    if rows:
                        conn.commit()
                        print(f"[Migration] backfilled {len(rows)} old memories")
                except Exception as e:
                    print(f"[Migration] worker error: {e}")
                await asyncio.sleep(30)

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_worker())

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        print("[Migration] background worker started")

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
