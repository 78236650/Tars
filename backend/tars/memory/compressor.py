"""Memory compression engine for manual merge and scheduled compaction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def _memory_to_dict(memory) -> Dict[str, Any]:
    entity_refs = []
    for ref in (memory.entity_refs or []):
        entity_refs.append(ref.get("name", str(ref)) if isinstance(ref, dict) else ref)
    return {
        "id": memory.id,
        "content": memory.content,
        "category": memory.category,
        "importance": memory.importance,
        "created_at": memory.created_at.isoformat() if memory.created_at else None,
        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
        "source": memory.source,
        "pinned": memory.pinned,
        "memory_type": memory.memory_type,
        "compressed_from": memory.compressed_from or [],
        "entity_refs": entity_refs,
        "event_time": memory.event_time.isoformat() if memory.event_time else None,
    }


@dataclass
class CompressionStatus:
    status: str = "idle"
    running: bool = False
    last_started_at: Optional[str] = None
    last_finished_at: Optional[str] = None
    last_report: Optional[Dict[str, Any]] = None
    progress: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "running": self.running,
            "last_started_at": self.last_started_at,
            "last_finished_at": self.last_finished_at,
            "last_report": self.last_report,
            "progress": self.progress,
        }


class MemoryCompressor:
    def __init__(self, db, provider=None, tenant_id: str = "default"):
        self.db = db
        self.provider = provider
        self.tenant_id = tenant_id
        self._status = CompressionStatus()

    def status(self) -> Dict[str, Any]:
        return self._status.to_dict()

    async def merge_memories(self, memory_ids: List[str], preview_only: bool = False) -> Dict[str, Any]:
        memories = [self.db.get_memory(memory_id, tenant_id=self.tenant_id) for memory_id in memory_ids]
        memories = [memory for memory in memories if memory is not None]
        if len(memories) < 2:
            raise ValueError("至少需要 2 条记忆才能合并")

        merged_content = await self._summarize(memories)
        max_importance = max(memory.importance or 0.5 for memory in memories)
        entity_refs = self._collect_entity_refs(memories)
        memory_type = "longterm" if max_importance >= 0.6 else "episodic"
        preview_payload = {
            "preview_only": preview_only,
            "merged_content": merged_content,
            "source_memory_ids": [memory.id for memory in memories],
            "importance": max_importance,
            "memory_type": memory_type,
            "entity_refs": entity_refs,
        }
        if preview_only:
            return preview_payload

        new_memory = self.db.add_memory(
            content=merged_content,
            category=memories[0].category,
            importance=max_importance,
            source="compression",
            compressed_from=[memory.id for memory in memories],
            memory_type=memory_type,
            entity_refs=entity_refs,
            tenant_id=self.tenant_id,
        )
        for memory in memories:
            self.db.delete_memory(memory.id, tenant_id=self.tenant_id)

        preview_payload["memory"] = _memory_to_dict(new_memory)
        return preview_payload

    async def compress_all(self) -> Dict[str, Any]:
        self._status.status = "running"
        self._status.running = True
        self._status.last_started_at = _now_iso()
        compressed_count = 0
        cleaned_count = 0
        entities = self._collect_entities_over_threshold()
        self._status.progress = {
            "entities_total": len(entities),
            "entities_done": 0,
        }

        try:
            for entity_id in entities:
                compressed_count += await self.compress_entity_memories(entity_id)
                self._status.progress["entities_done"] += 1

            cleaned_count = self.db.cleanup_old_memories(min_importance=0.25, max_age_days=15)
            report = {
                "status": "completed",
                "compressed_count": compressed_count,
                "cleaned_count": cleaned_count,
                "entities": entities,
            }
            self._status.status = "completed"
            self._status.last_finished_at = _now_iso()
            self._status.last_report = report
            return report
        except Exception as exc:
            report = {
                "status": "failed",
                "error": str(exc),
                "compressed_count": compressed_count,
                "cleaned_count": cleaned_count,
            }
            self._status.status = "failed"
            self._status.last_finished_at = _now_iso()
            self._status.last_report = report
            raise
        finally:
            self._status.running = False

    async def compress_entity_memories(self, entity_id: str) -> int:
        memories = self._fetch_entity_memories(entity_id)
        if len(memories) <= 10:
            return 0

        compressed = 0
        batch_size = 10
        for index in range(0, len(memories), batch_size):
            batch = memories[index : index + batch_size]
            if len(batch) < 2:
                continue
            await self.merge_memories([memory.id for memory in batch], preview_only=False)
            compressed += 1
        return compressed

    def _fetch_entity_memories(self, entity_id: str):
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id, tenant_id, content, category, importance, created_at, updated_at,
                last_accessed, source, pinned, compressed_from, memory_type, entity_refs, event_time
            FROM memories
            WHERE tenant_id = ?
              AND pinned = 0
              AND COALESCE(importance, 0.5) < 0.6
              AND entity_refs LIKE ?
            ORDER BY datetime(COALESCE(event_time, created_at)) ASC
            """,
            (self.tenant_id, f"%{entity_id}%"),
        )
        return [self.db._memory_from_row(row) for row in cursor.fetchall()]

    def _collect_entities_over_threshold(self) -> List[str]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT entity_refs
            FROM memories
            WHERE tenant_id = ? AND entity_refs IS NOT NULL AND pinned = 0
            """,
            (self.tenant_id,),
        )
        counts: Dict[str, int] = {}
        for (raw_refs,) in cursor.fetchall():
            try:
                refs = (raw_refs and __import__("json").loads(raw_refs)) or []
            except Exception:
                refs = []
            for ref in refs:
                if isinstance(ref, dict):
                    key = ref.get("name", str(ref))
                else:
                    key = str(ref) if ref else None
                if key:
                    counts[key] = counts.get(key, 0) + 1
        return [entity_id for entity_id, count in counts.items() if count > 10]

    async def _summarize(self, memories) -> str:
        lines = [f"{idx + 1}. {memory.content}" for idx, memory in enumerate(memories)]
        prompt = (
            "你是记忆压缩器。将以下多条记忆合并为一条精炼摘要：\n"
            "- 保留关键事实、决策、偏好\n"
            "- 去除重复和琐碎细节\n"
            "- 保持时间线顺序感\n"
            "- 输出不超过 200 字\n\n"
            + "\n".join(lines)
        )
        if self.provider:
            try:
                result = await self.provider.chat(
                    [{"role": "user", "content": prompt}],
                    temperature=0.2,
                )
                content = (result or {}).get("content", "").strip()
                if content:
                    return content[:200]
            except Exception:
                pass

        merged = "；".join(memory.content.strip() for memory in memories if memory.content.strip())
        return merged[:200]

    @staticmethod
    def _collect_entity_refs(memories) -> List[str]:
        seen: set = set()
        merged: List[str] = []
        for memory in memories:
            for entity_ref in memory.entity_refs or []:
                key = entity_ref.get("name", str(entity_ref)) if isinstance(entity_ref, dict) else str(entity_ref)
                if key and key not in seen:
                    seen.add(key)
                    merged.append(key)
        return merged
