"""记忆管理器 V3 — 整合 Core + Archival + Reflector"""
from typing import Optional, List

from .core_memory import CoreMemoryManager, CoreMemoryAppendTool, CoreMemoryReplaceTool
from .archival import ArchivalManager
from .reflector import Reflector
from .search import HybridSearch
from .embeddings import EmbeddingProvider
from .compressor import MemoryCompressor
from ..org import ORG_ID


class MemoryManager:
    """V3 记忆管理器：core memory + archival memory + reflector"""

    def __init__(
        self,
        db,
        provider=None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        tenant_id: str = ORG_ID,
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
        """构建注入 system prompt 的记忆上下文：core memory + 检索 + 实体图关联发现"""
        parts = []

        # Core memory（始终注入）
        core_render = self.core.render_for_prompt()
        if core_render.strip():
            parts.append(core_render)

        # Archival memory（语义+关键词检索）
        memories = self.search.search(query, limit)
        seen_ids: set = set()
        if memories:
            parts.append("\n## 相关长期记忆")
            for mem in memories:
                parts.append(f"- [{mem.category}] {mem.content}")
                seen_ids.add(mem.id)

        # ── v5.0.5/A3: 实体图关联发现 ──
        cross_memories = self._cross_entity_discovery(memories, seen_ids, limit=max(2, limit // 2))
        if cross_memories:
            parts.append("\n## 关联发现")
            for mem in cross_memories:
                parts.append(f"- [{mem.category}] {mem.content}")

        # ── v5.0.5/A3: 主动记忆提醒 ──
        proactive = self._proactive_reminders(query, seen_ids, limit=2)
        if proactive:
            parts.append("\n## 主动提醒\n以下是你可能需要的相关历史：")
            parts.append(proactive)
        return "\n".join(parts)

    def _cross_entity_discovery(self, source_memories, seen_ids: set, limit: int = 2):
        """通过实体关系图发现关联记忆。"""
        if not source_memories or not self.db:
            return []

        import json
        entity_ids: set = set()
        for mem in source_memories:
            refs = getattr(mem, "entity_refs", None)
            if not refs:
                continue
            if isinstance(refs, str):
                try:
                    refs = json.loads(refs)
                except Exception:
                    continue
            for ref in (refs or []):
                eid = ref if isinstance(ref, str) else (ref.get("name") or str(ref))
                if eid:
                    entity_ids.add(str(eid))

        if not entity_ids:
            return []

        # 查询关联实体
        related: set = set()
        try:
            conn = self.db._get_conn()
            cur = conn.cursor()
            for eid in entity_ids:
                cur.execute(
                    "SELECT from_entity, to_entity FROM relations "
                    "WHERE tenant_id = ? AND (from_entity = ? OR to_entity = ?)",
                    (self.tenant_id, eid, eid),
                )
                for from_e, to_e in cur.fetchall():
                    if from_e and from_e not in entity_ids:
                        related.add(from_e)
                    if to_e and to_e not in entity_ids:
                        related.add(to_e)
        except Exception:
            pass

        if not related:
            return []

        # 用关联实体检索记忆
        try:
            return self.db.get_recent_memories_for_entity(
                list(related), limit=limit, tenant_id=self.tenant_id
            )
        except Exception:
            return []



    def _proactive_reminders(self, query: str, seen_ids: set, limit: int = 2) -> str:
        """主动检索高价值历史记忆作为提醒。

        优先检索 solution（解决思路）和 pinned（用户标记重要）类记忆，
        让 Agent 在对话中主动引用相关历史，而非被动等待用户询问。
        """
        parts = []
        try:
            # 1. 检索 solution（解决思路）类 — 最高优先级
            conn = self.db._get_conn()
            cur = conn.cursor()
            cur.execute(
                """SELECT content FROM memories
                   WHERE tenant_id = ? AND category = 'solution'
                   ORDER BY importance DESC, updated_at DESC
                   LIMIT ?""",
                (self.tenant_id, limit),
            )
            for (content,) in cur.fetchall():
                if content and content not in seen_ids:
                    parts.append(f"- 💡 解决思路：{content[:120]}")
                    seen_ids.add(content[:80])

            # 2. 检索 pinned 记忆
            cur.execute(
                """SELECT content FROM memories
                   WHERE tenant_id = ? AND pinned = 1
                   ORDER BY updated_at DESC
                   LIMIT ?""",
                (self.tenant_id, limit),
            )
            for (content,) in cur.fetchall():
                if content and content[:80] not in seen_ids:
                    parts.append(f"- 📌 重要：{content[:120]}")
                    seen_ids.add(content[:80])

            # 3. 近期高 importance 决策
            cur.execute(
                """SELECT content FROM memories
                   WHERE tenant_id = ? AND importance >= 0.6
                   ORDER BY updated_at DESC
                   LIMIT ?""",
                (self.tenant_id, limit),
            )
            for (content,) in cur.fetchall():
                if content and content[:80] not in seen_ids:
                    parts.append(f"- 🔑 关键决策：{content[:120]}")
                    seen_ids.add(content[:80])

        except Exception:
            pass

        return "\n".join(parts[:limit * 2]) if parts else ""
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

    # ------------------------------------------------------------------
    # Markdown import/export
    # ------------------------------------------------------------------
    def export_markdown(self) -> str:
        """Serialize all memories (core + archival) into structured Markdown."""
        from datetime import datetime, timezone, timedelta

        lines = [
            "# TARS Memory Export",
            f"<!-- exported: {datetime.now(timezone(timedelta(hours=8))).isoformat()} -->",
            f"<!-- tenant: {self.tenant_id} -->",
            "",
        ]

        core_render = self.core.render_for_prompt()
        if core_render.strip():
            lines.append(core_render.strip())
            lines.append("")

        items, _total = self.db.list_all_memories(
            page=1, page_size=5000, tenant_id=self.tenant_id
        )
        if items:
            lines.append("## 长期记忆")
            lines.append("")
            for mem in items:
                created = (
                    mem.created_at.isoformat() if hasattr(mem.created_at, "isoformat")
                    else str(mem.created_at) if mem.created_at else ""
                )
                imp = getattr(mem, "importance", 0)
                category = getattr(mem, "category", "fact")
                content = (mem.content or "").replace("\n", " ")
                lines.append(
                    f"- [{category}] {content} "
                    f"<!-- importance:{imp:.2f} created:{created} id:{mem.id} -->"
                )
            lines.append("")

        return "\n".join(lines)

    def import_markdown(self, markdown_text: str) -> dict:
        """Parse Markdown and insert archival memories.

        Recognizes `## 长期记忆` section with `- [category] content` bullets.
        Returns {"imported": int, "skipped": int}.
        """
        import re

        imported = 0
        skipped = 0

        section_match = re.search(
            r"^##\s+长期记忆\s*\n(.*?)(?=\n##|\Z)",
            markdown_text,
            re.DOTALL | re.MULTILINE,
        )
        if not section_match:
            return {"imported": 0, "skipped": 0, "reason": "no 长期记忆 section found"}

        section = section_match.group(1)
        bullet_re = re.compile(
            r"^-\s*\[(\w+)\]\s+(.+?)\s*(<!--.*?-->)?\s*$",
            re.MULTILINE,
        )
        for m in bullet_re.finditer(section):
            category = m.group(1).strip()
            content = m.group(2).strip()
            annotation = m.group(3) or ""

            if len(content) < 3:
                skipped += 1
                continue

            importance = 0.5
            imp_match = re.search(r"importance:([\d.]+)", annotation)
            if imp_match:
                try:
                    importance = float(imp_match.group(1))
                except ValueError:
                    pass

            allowed = {"fact", "preference", "decision", "domain_knowledge"}
            if category not in allowed:
                category = "fact"

            try:
                self.archival.insert(
                    content, category, importance=importance, source="markdown_import"
                )
                imported += 1
            except Exception:
                skipped += 1

        return {"imported": imported, "skipped": skipped}

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
