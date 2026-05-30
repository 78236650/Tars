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

    _EXTRACT_CATEGORY_MAP = {
        "user_preference": "preference",
        "important_decision": "decision",
        "project_record": "fact",
        "general": "fact",
        "preference": "preference",
        "decision": "decision",
        "fact": "fact",
        "domain_knowledge": "domain_knowledge",
    }

    async def extract_turn_memories(self, user_msg: str, assistant_msg: str) -> List[dict]:
        """从单轮对话提取可保存的记忆要点（供前端预览确认）。"""
        from .extractor import (
            HeuristicTurnExtractor,
            LLMMemoryExtractor,
            RegexExtractor,
            TURN_EXTRACTION_PROMPT,
        )

        user_msg = (user_msg or "").strip()
        assistant_msg = (assistant_msg or "").strip()
        if not assistant_msg:
            return []

        conversation = f"User: {user_msg}\nAssistant: {assistant_msg}"
        extractor = LLMMemoryExtractor()
        raw = await extractor.extract(
            conversation,
            self.provider,
            prompt_template=TURN_EXTRACTION_PROMPT,
        )
        if not raw:
            raw = HeuristicTurnExtractor().extract(user_msg, assistant_msg)
        if not raw:
            raw = RegexExtractor().extract(conversation)

        items: List[dict] = []
        seen = set()
        for entry in raw:
            content = str(entry.get("content", "")).strip()
            if len(content) < 5:
                continue
            key = content.lower()
            if key in seen:
                continue
            seen.add(key)
            raw_category = str(entry.get("category", "general"))
            items.append(
                {
                    "content": content,
                    "category": self._EXTRACT_CATEGORY_MAP.get(raw_category, "fact"),
                    "importance": float(entry.get("importance", 0.75)),
                }
            )
        return items[:8]

    async def save_turn_memories(
        self,
        items: List[dict],
        *,
        user_context: str = "",
        publish_to_knowledge: bool = False,
        promotion_group_id: Optional[str] = None,
    ) -> dict:
        """保存用户确认后的记忆要点。默认仅写 episodic 记忆；KB 需显式发布或达阈值自动升格。"""
        from .kb_promotion import default_promotion_group_id, promote_group_to_kb

        saved = []
        skipped = 0
        allowed = set(self._EXTRACT_CATEGORY_MAP.values())
        group_id = promotion_group_id or default_promotion_group_id(self.tenant_id)
        saved_ids: List[str] = []

        for item in items:
            content = str(item.get("content", "")).strip()
            if len(content) < 5:
                skipped += 1
                continue
            category = str(item.get("category", "fact"))
            if category not in allowed:
                category = "fact"
            importance = float(item.get("importance", 0.75))
            mem = await self.archival.insert(
                content,
                category,
                importance=importance,
                source="manual_extract",
            )
            if mem:
                self.db.set_memory_promotion_meta(
                    mem.id,
                    tenant_id=self.tenant_id,
                    promotion_group_id=group_id,
                    kb_promotion_status="pending",
                    memory_type="episodic",
                )
                saved.append(mem)
                saved_ids.append(mem.id)
            else:
                skipped += 1

        knowledge_doc_ids: List[str] = []
        promotion_trigger = "none"

        if publish_to_knowledge and saved_ids:
            from ..config.memory import config

            if config.kb_promotion_enabled:
                doc_id = await promote_group_to_kb(
                    self,
                    group_id,
                    user_context=user_context,
                    memory_ids=saved_ids,
                )
                if doc_id:
                    knowledge_doc_ids.append(doc_id)
                    promotion_trigger = "manual"
        elif saved_ids:
            promotion_trigger = "pending"

        return {
            "saved": saved,
            "skipped": skipped,
            "knowledge_doc_ids": knowledge_doc_ids,
            "promotion_group_id": group_id,
            "promotion_trigger": promotion_trigger,
        }

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
        """返回需要注册到 ToolRegistry 的工具列表（按 tenant_id 隔离写入）"""
        return [
            CoreMemoryAppendTool(self.db),
            CoreMemoryReplaceTool(self.db),
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
