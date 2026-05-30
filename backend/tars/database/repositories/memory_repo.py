# TARS Memory Repository
# Auto-extracted from base.py

import json
import uuid
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from tars.database.models import (
    get_local_now, _parse_db_datetime,
    Session, Message, Memory, CronJob,
    ReminderNotification, Transcription, AuditLog, ApprovalRequest,
)
from tars.database.connection import ConnectionManager
from tars.database.sql_dialect import fulltext_match_clause, placeholder
from tars.org import ORG_ID

_MEMORY_SELECT = """
    id, tenant_id, content, category, importance, created_at, updated_at,
    last_accessed, source, pinned, compressed_from, memory_type, entity_refs, event_time, scope,
    promotion_group_id, kb_doc_id, kb_promotion_status, user_id
"""


class MemoryRepo:
    """Memory 域 Repository。"""

    def __init__(self, cm: ConnectionManager):
        self._cm = cm

    @staticmethod
    def _resolve_viewer_user_id(user_id: Optional[str] = None) -> Optional[str]:
        if user_id is not None:
            return user_id
        try:
            from tars.context import get_current_user_id
            return get_current_user_id()
        except RuntimeError:
            return None

    @staticmethod
    def _resolve_writer_user_id(user_id: Optional[str], scope: str) -> Optional[str]:
        if scope == "shared":
            return None
        if user_id is not None:
            return user_id
        try:
            from tars.context import get_current_user_id
            return get_current_user_id()
        except RuntimeError:
            return None

    def _visibility_clause(self, user_id: Optional[str] = None) -> Tuple[str, List[Any]]:
        viewer = self._resolve_viewer_user_id(user_id)
        if viewer is None:
            return "tenant_id = ? AND (scope = 'shared' OR user_id IS NULL)", [ORG_ID]
        return "tenant_id = ? AND (scope = 'shared' OR user_id = ?)", [ORG_ID, viewer]

    def _get_conn(self):
        return self._cm.get_conn()

    def _fts_enabled(self) -> bool:
        return self._cm.dialect == "sqlite"

    def add_memory(
        self,
        content: str,
        category: str = "general",
        importance: float = 0.5,
        embedding: bytes = None,
        source: str = "conversation",
        pinned: bool = False,
        compressed_from: Optional[List[str]] = None,
        memory_type: str = "episodic",
        event_time: Optional[str] = None,
        entity_refs: Optional[List[str]] = None,
        tenant_id: str = ORG_ID,
        scope: str = "private",
        user_id: Optional[str] = None,
    ) -> Memory:
        memory_id = str(uuid.uuid4())
        now = get_local_now()
        event_time_value = event_time or now.isoformat()
        entity_refs_json = json.dumps(entity_refs, ensure_ascii=False) if entity_refs is not None else None
        compressed_from_json = (
            json.dumps(compressed_from, ensure_ascii=False) if compressed_from is not None else None
        )
        resolved_tenant_id = tenant_id or ORG_ID
        resolved_user_id = self._resolve_writer_user_id(user_id, scope)

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memories
            (
                id, tenant_id, user_id, content, category, importance, created_at, updated_at,
                last_accessed, embedding, access_count, source, event_time, entity_refs,
                pinned, compressed_from, memory_type, scope
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                resolved_tenant_id,
                resolved_user_id,
                content,
                category,
                importance,
                now,
                now,
                None,
                embedding,
                0,
                source,
                event_time_value,
                entity_refs_json,
                1 if pinned else 0,
                compressed_from_json,
                memory_type,
                scope,
            ),
        )

        if self._fts_enabled():
            cursor.execute(
                "INSERT INTO memories_fts(rowid, content, category) VALUES (last_insert_rowid(), ?, ?)",
                (content, category),
            )

        conn.commit()

        return Memory(
            id=memory_id,
            content=content,
            category=category,
            tenant_id=resolved_tenant_id,
            user_id=resolved_user_id,
            importance=importance,
            created_at=now,
            updated_at=now,
            source=source,
            pinned=bool(pinned),
            compressed_from=compressed_from,
            memory_type=memory_type,
            event_time=_parse_db_datetime(event_time_value),
            entity_refs=entity_refs,
            scope=scope,
        )

    def _memory_from_row(self, row) -> Memory:
        if row is None:
            return None
        compressed_from = json.loads(row[10]) if row[10] else None
        entity_refs = json.loads(row[12]) if row[12] else None
        return Memory(
            id=row[0],
            tenant_id=row[1],
            content=row[2],
            category=row[3],
            importance=row[4],
            created_at=_parse_db_datetime(row[5]),
            updated_at=_parse_db_datetime(row[6]),
            last_accessed=_parse_db_datetime(row[7]) if row[7] else None,
            source=row[8] or "conversation",
            pinned=bool(row[9]),
            compressed_from=compressed_from,
            memory_type=row[11] or "episodic",
            event_time=_parse_db_datetime(row[13]) if row[13] else None,
            entity_refs=entity_refs,
            scope=row[14] if len(row) > 14 and row[14] else "private",
            promotion_group_id=row[15] if len(row) > 15 else None,
            kb_doc_id=row[16] if len(row) > 16 else None,
            kb_promotion_status=row[17] if len(row) > 17 else None,
            user_id=row[18] if len(row) > 18 else None,
        )

    def get_memory(
        self,
        memory_id: str,
        tenant_id: str = ORG_ID,
        user_id: Optional[str] = None,
    ) -> Optional[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT {_MEMORY_SELECT}
            FROM memories
            WHERE id = ? AND tenant_id = ?
            """,
            (memory_id, tenant_id or ORG_ID),
        )
        memory = self._memory_from_row(cursor.fetchone())
        if memory is None:
            return None
        if memory.scope == "private":
            viewer = self._resolve_viewer_user_id(user_id)
            if memory.user_id != viewer:
                return None
        return memory

    @staticmethod
    def _has_cjk(text: str) -> bool:
        """检查文本是否包含 CJK 字符"""
        for ch in text:
            cp = ord(ch)
            if (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
                0x3000 <= cp <= 0x303F or 0xFF00 <= cp <= 0xFFEF or
                0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF or
                0xAC00 <= cp <= 0xD7AF):
                return True
        return False

    def _like_op(self) -> str:
        return "ILIKE" if self._cm.dialect == "postgres" else "LIKE"

    def _table_exists(self, cursor, table: str) -> bool:
        if self._cm.dialect == "sqlite":
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            return cursor.fetchone() is not None
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = ?
            )
            """,
            (table,),
        )
        row = cursor.fetchone()
        return bool(row and row[0])

    def _rows_to_memories(self, rows) -> List[Memory]:
        memories: List[Memory] = []
        for row in rows:
            memories.append(
                Memory(
                    id=row[0],
                    tenant_id=row[1],
                    content=row[2],
                    category=row[3],
                    importance=row[4],
                    created_at=datetime.fromisoformat(row[5]),
                    updated_at=datetime.fromisoformat(row[6]),
                    last_accessed=datetime.fromisoformat(row[7]) if row[7] else None,
                )
            )
        return memories

    def _search_memories_like(
        self,
        cursor,
        visibility: str,
        vis_params: List[Any],
        query: str,
        limit: int,
    ) -> List[Memory]:
        ph = placeholder(self._cm.dialect)
        like_op = self._like_op()
        cursor.execute(
            f"""
            SELECT id, tenant_id, content, category, importance, created_at, updated_at, last_accessed
            FROM memories
            WHERE {visibility} AND content {like_op} {ph}
            ORDER BY importance DESC, updated_at DESC
            LIMIT {ph}
            """,
            (*vis_params, f"%{query}%", limit),
        )
        return self._rows_to_memories(cursor.fetchall())

    def search_memories(
        self,
        query: str,
        limit: int = 5,
        tenant_id: str = ORG_ID,
        user_id: Optional[str] = None,
    ) -> List[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()
        visibility, vis_params = self._visibility_clause(user_id)
        ph = placeholder(self._cm.dialect)

        # 转义 FTS5 特殊字符
        safe_query = query.replace('"', ' ').replace('*', ' ').replace('^', ' ')
        safe_query = safe_query.replace(':', ' ').replace('(', ' ').replace(')', ' ').replace('-', ' ').strip()
        has_cjk = self._has_cjk(query)

        memories: List[Memory] = []
        dialect = self._cm.dialect

        # 1. SQLite FTS5（Postgres 无 memories_fts 虚表，跳过 JOIN 路径）
        if safe_query and dialect == "sqlite" and self._table_exists(cursor, "memories_fts"):
            try:
                fts_clause = fulltext_match_clause(dialect, "fts", ph)
                cursor.execute(
                    f"""
                    SELECT m.id, m.tenant_id, m.content, m.category, m.importance,
                           m.created_at, m.updated_at, m.last_accessed
                    FROM memories m
                    JOIN memories_fts fts ON m.rowid = fts.rowid
                    WHERE {fts_clause} AND {visibility}
                    ORDER BY rank
                    LIMIT {ph}
                    """,
                    (safe_query, *vis_params, limit),
                )
                memories = self._rows_to_memories(cursor.fetchall())
            except sqlite3.OperationalError:
                pass

        # 2. Postgres 全文（content 列 to_tsvector，无 FTS 虚表）
        if not memories and safe_query and dialect == "postgres":
            try:
                fts_clause = fulltext_match_clause(dialect, "m.content", ph)
                cursor.execute(
                    f"""
                    SELECT m.id, m.tenant_id, m.content, m.category, m.importance,
                           m.created_at, m.updated_at, m.last_accessed
                    FROM memories m
                    WHERE {fts_clause} AND {visibility}
                    ORDER BY m.importance DESC, m.updated_at DESC
                    LIMIT {ph}
                    """,
                    (safe_query, *vis_params, limit),
                )
                memories = self._rows_to_memories(cursor.fetchall())
            except Exception:
                pass

        # 3. CJK 或 PG 兜底：ILIKE / LIKE
        if not memories and (has_cjk or dialect == "postgres"):
            try:
                memories = self._search_memories_like(
                    cursor, visibility, vis_params, query, limit
                )
            except Exception:
                pass

        # 4. 空结果兜底：通用 LIKE / ILIKE
        if not memories:
            try:
                memories = self._search_memories_like(
                    cursor, visibility, vis_params, query, limit
                )
            except Exception:
                pass

        for mem in memories:
            self._update_memory_access(mem.id)

        return memories

    def get_memories_by_category(
        self,
        category: str,
        limit: int = 10,
        tenant_id: str = ORG_ID,
        user_id: Optional[str] = None,
    ) -> List[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()
        visibility, vis_params = self._visibility_clause(user_id)
        cursor.execute(f"""
            SELECT id, tenant_id, content, category, importance, created_at, updated_at, last_accessed
            FROM memories
            WHERE {visibility} AND category = ?
            ORDER BY importance DESC, updated_at DESC
            LIMIT ?
        """, (*vis_params, category, limit))

        memories = []
        for row in cursor.fetchall():
            memories.append(Memory(
                id=row[0],
                tenant_id=row[1],
                content=row[2],
                category=row[3],
                importance=row[4],
                created_at=datetime.fromisoformat(row[5]),
                updated_at=datetime.fromisoformat(row[6]),
                last_accessed=datetime.fromisoformat(row[7]) if row[7] else None
            ))

        return memories

    def get_recent_memories(
        self,
        limit: int = 20,
        tenant_id: str = ORG_ID,
        user_id: Optional[str] = None,
    ) -> List[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()
        visibility, vis_params = self._visibility_clause(user_id)
        cursor.execute(f"""
            SELECT id, tenant_id, content, category, importance, created_at, updated_at, last_accessed
            FROM memories
            WHERE {visibility}
            ORDER BY updated_at DESC
            LIMIT ?
        """, (*vis_params, limit))

        memories = []
        for row in cursor.fetchall():
            memories.append(Memory(
                id=row[0],
                tenant_id=row[1],
                content=row[2],
                category=row[3],
                importance=row[4],
                created_at=datetime.fromisoformat(row[5]),
                updated_at=datetime.fromisoformat(row[6]),
                last_accessed=datetime.fromisoformat(row[7]) if row[7] else None
            ))

        return memories

    def update_memory(
        self,
        memory_id: str,
        content: str,
        importance: float = None,
        category: Optional[str] = None,
        pinned: Optional[bool] = None,
        compressed_from: Optional[List[str]] = None,
        memory_type: Optional[str] = None,
        event_time: Optional[str] = None,
        entity_refs: Optional[List[str]] = None,
        tenant_id: str = ORG_ID,
    ):
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()
        sets = ["content = ?", "updated_at = ?"]
        values: List[Any] = [content, now]
        if importance is not None:
            sets.append("importance = ?")
            values.append(importance)
        if category is not None:
            sets.append("category = ?")
            values.append(category)
        if pinned is not None:
            sets.append("pinned = ?")
            values.append(1 if pinned else 0)
        if compressed_from is not None:
            sets.append("compressed_from = ?")
            values.append(json.dumps(compressed_from, ensure_ascii=False))
        if memory_type is not None:
            sets.append("memory_type = ?")
            values.append(memory_type)
        if event_time is not None:
            sets.append("event_time = ?")
            values.append(event_time)
        if entity_refs is not None:
            sets.append("entity_refs = ?")
            values.append(json.dumps(entity_refs, ensure_ascii=False))
        values.extend([memory_id, tenant_id])
        cursor.execute(
            f"""
            UPDATE memories
            SET {", ".join(sets)}
            WHERE id = ? AND tenant_id = ?
            """,
            values,
        )

        if self._fts_enabled():
            cursor.execute(
                """
                UPDATE memories_fts
                SET content = ?, category = COALESCE(?, category)
                WHERE rowid = (SELECT rowid FROM memories WHERE id = ? AND tenant_id = ?)
                """,
                (content, category, memory_id, tenant_id),
            )

        conn.commit()
        return cursor.rowcount > 0

    def reinforce_memory(self, memory_id: str, importance_delta: float = 0.02, tenant_id: str = ORG_ID):
        """命中召回：access_count+1, last_accessed=now, importance 微增"""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = get_local_now()
        cursor.execute(
            """
            UPDATE memories
            SET access_count = COALESCE(access_count, 0) + 1,
                last_accessed = ?,
                importance = MIN(1.0, COALESCE(importance, 0.5) + ?)
            WHERE id = ? AND tenant_id = ?
            """,
            (now, importance_delta, memory_id, tenant_id),
        )
        conn.commit()

    def get_all_memories_with_metadata(self, tenant_id: str = ORG_ID):
        """返回 (Memory, embedding_blob, last_accessed_iso, importance, source) 列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tenant_id, content, category, importance, created_at, updated_at, embedding, last_accessed, source
            FROM memories WHERE tenant_id = ?
            """,
            (tenant_id,),
        )
        results = []
        for row in cursor.fetchall():
            mem = Memory(
                id=row[0], tenant_id=row[1], content=row[2], category=row[3], importance=row[4],
                created_at=row[5], updated_at=row[6],
            )
            last_accessed_str = str(row[8]) if row[8] else (str(row[5]) if row[5] else "")
            results.append((mem, row[7], last_accessed_str, row[4] or 0.5, row[9] or "conversation"))
        return results

    def set_memory_pin(self, memory_id: str, pinned: bool, tenant_id: str = ORG_ID) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE memories SET pinned = ?, updated_at = ? WHERE id = ? AND tenant_id = ?",
            (1 if pinned else 0, get_local_now(), memory_id, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def promote_memory(
        self,
        memory_id: str,
        tenant_id: str = ORG_ID,
        user_id: Optional[str] = None,
    ) -> Optional[Memory]:
        if self.get_memory(memory_id, tenant_id=tenant_id, user_id=user_id) is None:
            return None
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE memories
            SET memory_type = 'longterm',
                importance = MAX(COALESCE(importance, 0.5), 0.6),
                updated_at = ?
            WHERE id = ? AND tenant_id = ?
            """,
            (get_local_now(), memory_id, tenant_id),
        )
        conn.commit()
        return self.get_memory(memory_id, tenant_id=tenant_id, user_id=user_id)

    def set_memory_promotion_meta(
        self,
        memory_id: str,
        *,
        tenant_id: str = ORG_ID,
        promotion_group_id: Optional[str] = None,
        kb_promotion_status: Optional[str] = None,
        kb_doc_id: Optional[str] = None,
        memory_type: Optional[str] = None,
    ) -> bool:
        sets = ["updated_at = ?"]
        values: List[Any] = [get_local_now()]
        if promotion_group_id is not None:
            sets.append("promotion_group_id = ?")
            values.append(promotion_group_id)
        if kb_promotion_status is not None:
            sets.append("kb_promotion_status = ?")
            values.append(kb_promotion_status)
        if kb_doc_id is not None:
            sets.append("kb_doc_id = ?")
            values.append(kb_doc_id)
        if memory_type is not None:
            sets.append("memory_type = ?")
            values.append(memory_type)
        values.extend([memory_id, tenant_id])
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE memories SET {', '.join(sets)} WHERE id = ? AND tenant_id = ?",
            values,
        )
        conn.commit()
        return cursor.rowcount > 0

    def get_kb_promotion_group_stats(self, tenant_id: str, promotion_group_id: str) -> Dict[str, Any]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(LENGTH(content)), 0)
            FROM memories
            WHERE tenant_id = ?
              AND source = 'manual_extract'
              AND promotion_group_id = ?
              AND (kb_promotion_status IS NULL OR kb_promotion_status = 'pending')
            """,
            (tenant_id, promotion_group_id),
        )
        row = cursor.fetchone()
        return {
            "count": int(row[0] or 0),
            "total_chars": int(row[1] or 0),
            "promotion_group_id": promotion_group_id,
        }

    def list_memories_for_kb_promotion(
        self,
        *,
        tenant_id: str,
        promotion_group_id: str,
        memory_ids: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()
        if memory_ids:
            placeholders = ",".join("?" for _ in memory_ids)
            cursor.execute(
                f"""
                SELECT id, tenant_id, content, category, importance, created_at, updated_at,
                       last_accessed, source, pinned, compressed_from, memory_type, entity_refs, event_time, scope,
                       promotion_group_id, kb_doc_id, kb_promotion_status
                FROM memories
                WHERE tenant_id = ? AND id IN ({placeholders})
                  AND source = 'manual_extract'
                  AND (kb_promotion_status IS NULL OR kb_promotion_status = 'pending')
                ORDER BY created_at ASC
                LIMIT ?
                """,
                [tenant_id, *memory_ids, limit],
            )
        else:
            cursor.execute(
                """
                SELECT id, tenant_id, content, category, importance, created_at, updated_at,
                       last_accessed, source, pinned, compressed_from, memory_type, entity_refs, event_time, scope,
                       promotion_group_id, kb_doc_id, kb_promotion_status
                FROM memories
                WHERE tenant_id = ?
                  AND source = 'manual_extract'
                  AND promotion_group_id = ?
                  AND (kb_promotion_status IS NULL OR kb_promotion_status = 'pending')
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (tenant_id, promotion_group_id, limit),
            )
        return [self._memory_from_row(row) for row in cursor.fetchall() if row]

    def mark_memories_kb_published(
        self,
        memory_ids: List[str],
        *,
        tenant_id: str,
        kb_doc_id: str,
    ) -> int:
        if not memory_ids:
            return 0
        conn = self._get_conn()
        cursor = conn.cursor()
        now = get_local_now()
        updated = 0
        for memory_id in memory_ids:
            cursor.execute(
                """
                UPDATE memories
                SET kb_promotion_status = 'published',
                    kb_doc_id = ?,
                    memory_type = 'longterm',
                    importance = MAX(COALESCE(importance, 0.5), 0.65),
                    updated_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (kb_doc_id, now, memory_id, tenant_id),
            )
            updated += cursor.rowcount
        conn.commit()
        return updated

    def list_kb_promotion_groups(self, limit: int = 200) -> List[tuple[str, str]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tenant_id, promotion_group_id
            FROM memories
            WHERE source = 'manual_extract'
              AND promotion_group_id IS NOT NULL
              AND (kb_promotion_status IS NULL OR kb_promotion_status = 'pending')
            GROUP BY tenant_id, promotion_group_id
            ORDER BY MAX(created_at) DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [(row[0], row[1]) for row in cursor.fetchall() if row[0] and row[1]]

    def delete_memory(self, memory_id: str, tenant_id: str = ORG_ID):
        conn = self._get_conn()
        cursor = conn.cursor()
        if self._fts_enabled():
            cursor.execute("SELECT rowid FROM memories WHERE id = ? AND tenant_id = ?", (memory_id, tenant_id))
            row = cursor.fetchone()
            if row:
                cursor.execute("DELETE FROM memories_fts WHERE rowid = ?", (row[0],))
        cursor.execute("DELETE FROM memories WHERE id = ? AND tenant_id = ?", (memory_id, tenant_id))
        conn.commit()
        return cursor.rowcount > 0

    def get_memory_stats(self, tenant_id: str = ORG_ID) -> Dict[str, Any]:
        conn = self._get_conn()
        cursor = conn.cursor()
        time_expr = "julianday(replace(substr(created_at, 1, 19), 'T', ' '))"
        cursor.execute(
            f"""
            SELECT
                COUNT(*),
                SUM(CASE WHEN memory_type = 'episodic' AND {time_expr} >= julianday('now', '-7 day') THEN 1 ELSE 0 END),
                SUM(CASE WHEN importance >= 0.6 OR pinned = 1 OR memory_type = 'longterm' THEN 1 ELSE 0 END)
            FROM memories WHERE tenant_id = ?
            """,
            (tenant_id,),
        )
        row = cursor.fetchone()
        total, recent, longterm = row[0], row[1] or 0, row[2] or 0
        cursor.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT entity_refs
                FROM memories
                WHERE tenant_id = ? AND entity_refs IS NOT NULL AND pinned = 0
                GROUP BY entity_refs
                HAVING COUNT(*) > 10
            )
            """,
            (tenant_id,),
        )
        pending = cursor.fetchone()[0]
        return {
            "total": total,
            "recent": recent,
            "longterm": longterm,
            "pending_compression": pending,
        }

    def list_recent_memories(
        self,
        page: int = 1,
        page_size: int = 20,
        query: str = "",
        category: str = "",
        tenant_id: str = ORG_ID,
        user_id: Optional[str] = None,
    ) -> Tuple[List[Memory], int]:
        conn = self._get_conn()
        cursor = conn.cursor()
        time_expr = "julianday(replace(substr(created_at, 1, 19), 'T', ' '))"
        visibility, vis_params = self._visibility_clause(user_id)
        clauses = [
            visibility,
            "memory_type = 'episodic'",
            f"{time_expr} >= julianday('now', '-7 day')",
        ]
        params: List[Any] = list(vis_params)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if query:
            clauses.append("content LIKE ?")
            params.append(f"%{query}%")
        where = " AND ".join(clauses)
        cursor.execute(f"SELECT COUNT(*) FROM memories WHERE {where}", params)
        total = cursor.fetchone()[0]
        offset = max(page - 1, 0) * page_size
        cursor.execute(
            f"""
            SELECT
                id, tenant_id, content, category, importance, created_at, updated_at,
                last_accessed, source, pinned, compressed_from, memory_type, entity_refs, event_time
            FROM memories
            WHERE {where}
            ORDER BY julianday(replace(substr(created_at, 1, 19), 'T', ' ')) DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        )
        items = [self._memory_from_row(row) for row in cursor.fetchall()]
        return items, total

    def list_longterm_memories(
        self,
        tenant_id: str = ORG_ID,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
    ) -> Tuple[List[Memory], int]:
        conn = self._get_conn()
        cursor = conn.cursor()
        visibility, vis_params = self._visibility_clause(user_id)
        where = f"{visibility} AND (importance >= 0.6 OR pinned = 1 OR memory_type = 'longterm')"
        cursor.execute(f"SELECT COUNT(*) FROM memories WHERE {where}", vis_params)
        total = cursor.fetchone()[0]
        offset = max(page - 1, 0) * page_size
        cursor.execute(
            f"""
            SELECT
                id, tenant_id, content, category, importance, created_at, updated_at,
                last_accessed, source, pinned, compressed_from, memory_type, entity_refs, event_time
            FROM memories
            WHERE {where}
            ORDER BY pinned DESC, importance DESC, updated_at DESC
            LIMIT ? OFFSET ?
            """,
            [*vis_params, page_size, offset],
        )
        return [self._memory_from_row(row) for row in cursor.fetchall()], total

    def list_all_memories(
        self,
        page: int = 1,
        page_size: int = 20,
        query: str = "",
        category: str = "",
        memory_type: str = "",
        tenant_id: str = ORG_ID,
        user_id: Optional[str] = None,
    ) -> Tuple[List[Memory], int]:
        conn = self._get_conn()
        cursor = conn.cursor()
        visibility, vis_params = self._visibility_clause(user_id)
        clauses = [visibility]
        params: List[Any] = list(vis_params)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if memory_type:
            clauses.append("memory_type = ?")
            params.append(memory_type)
        if query:
            clauses.append("content LIKE ?")
            params.append(f"%{query}%")
        where = " AND ".join(clauses)
        cursor.execute(f"SELECT COUNT(*) FROM memories WHERE {where}", params)
        total = cursor.fetchone()[0]
        offset = max(page - 1, 0) * page_size
        cursor.execute(
            f"""
            SELECT
                id, tenant_id, content, category, importance, created_at, updated_at,
                last_accessed, source, pinned, compressed_from, memory_type, entity_refs, event_time
            FROM memories
            WHERE {where}
            ORDER BY julianday(replace(substr(created_at, 1, 19), 'T', ' ')) DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        )
        items = [self._memory_from_row(row) for row in cursor.fetchall()]
        return items, total

    def list_memories_for_tree(self, tenant_id: str = ORG_ID, limit: int = 5000) -> List[Memory]:
        """Load tenant memories for entity tree assembly (bounded)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id, tenant_id, content, category, importance, created_at, updated_at,
                last_accessed, source, pinned, compressed_from, memory_type, entity_refs, event_time, scope
            FROM memories
            WHERE tenant_id = ?
            ORDER BY pinned DESC, importance DESC, updated_at DESC
            LIMIT ?
            """,
            (tenant_id, limit),
        )
        return [self._memory_from_row(row) for row in cursor.fetchall()]

    def decay_importance(self):
        """重要性自然衰减：未被访问的记忆重要性随时间微降"""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = get_local_now()
        # 超过 24 小时未访问的记忆，importance 每日衰减 0.01，不低于 0.1
        cursor.execute("""
            UPDATE memories
            SET importance = MAX(0.1, importance - 0.01 * CAST((julianday(?) - julianday(COALESCE(last_accessed, created_at))) AS INTEGER))
            WHERE COALESCE(last_accessed, created_at) < ?
        """, (now.isoformat(), (now - timedelta(hours=24)).isoformat()))
        count = cursor.rowcount
        conn.commit()
        return count

    def cleanup_old_memories(self, min_importance: float = 0.25, max_age_days: int = 15) -> int:
        """清理过期记忆：重要性低于阈值 + 超过指定天数未访问"""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = get_local_now()
        cutoff = now - timedelta(days=max_age_days)
        cursor.execute("""
            DELETE FROM memories
            WHERE importance < ?
              AND COALESCE(last_accessed, created_at) < ?
        """, (min_importance, cutoff.isoformat()))
        deleted = cursor.rowcount
        if deleted > 0 and self._fts_enabled():
            # 重建 FTS 索引
            cursor.execute("DELETE FROM memories_fts")
            cursor.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
        conn.commit()
        return deleted

    def forget_core_line(
        self,
        block: str,
        line_contains: str,
        tenant_id: str = ORG_ID,
        user_id: Optional[str] = None,
    ) -> bool:
        """从 core memory 区块中删除匹配的行"""
        resolved_user_id = self._resolve_viewer_user_id(user_id) or "default"
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT content FROM core_memory_blocks
            WHERE name = ? AND tenant_id = ? AND user_id = ?
            """,
            (block, tenant_id, resolved_user_id),
        )
        row = cursor.fetchone()
        if not row:
            return False
        content = row[0]
        lines = content.split("\n")
        new_lines = [l for l in lines if line_contains not in l]
        if len(new_lines) == len(lines):
            return False
        new_content = "\n".join(new_lines)
        now = get_local_now().isoformat()
        cursor.execute(
            """
            UPDATE core_memory_blocks SET content = ?, updated_at = ?
            WHERE name = ? AND tenant_id = ? AND user_id = ?
            """,
            (new_content, now, block, tenant_id, resolved_user_id),
        )
        conn.commit()
        return True

    def _update_memory_access(self, memory_id: str):
        now = get_local_now()
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE memories SET last_accessed = ? WHERE id = ?",
            (now, memory_id)
        )
        conn.commit()

    def get_all_memories_with_embeddings(self) -> List[Tuple]:
        """获取所有记忆及其嵌入向量（用于语义搜索）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, content, category, importance, created_at, updated_at, last_accessed, embedding
            FROM memories
            ORDER BY updated_at DESC
        """)
        results = []
        for row in cursor.fetchall():
            mem = Memory(
                id=row[0], content=row[1], category=row[2], importance=row[3],
                created_at=datetime.fromisoformat(row[4]),
                updated_at=datetime.fromisoformat(row[5]),
                last_accessed=datetime.fromisoformat(row[6]) if row[6] else None,
            )
            results.append((mem, row[7]))  # (Memory, embedding_blob)
        return results

    # ============ CronJob 定时任务方法 ============
    def add_dead_letter(self, op: str, error: str, session_id: str = None):
        conn = self._get_conn()
        cur = conn.cursor()
        now = get_local_now().isoformat()
        cur.execute(
            "INSERT INTO dead_letter_queue (op, error, session_id, created_at) VALUES (?, ?, ?, ?)",
            (op, error, session_id, now),
        )
        conn.commit()

    # ============ Meeting Voice Recognition ============

    def set_memory_scope(self, memory_id: str, scope: str, tenant_id: str = ORG_ID) -> bool:
        """Set scope for a memory (private/shared). Admin only."""
        if scope not in ("private", "shared"):
            return False
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE memories SET scope = ?, updated_at = ? WHERE id = ? AND tenant_id = ?",
            (scope, get_local_now(), memory_id, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def find_memory_any_tenant(self, memory_id: str) -> Optional[Memory]:
        """Find a memory by ID without tenant filter (for admin/cross-tenant lookup)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT {_MEMORY_SELECT}
            FROM memories WHERE id = ?
            """,
            (memory_id,),
        )
        row = cursor.fetchone()
        return self._memory_from_row(row)

    def get_memory_scope(self, memory_id: str, tenant_id: str = ORG_ID) -> str:
        """Return the scope of a memory."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT scope FROM memories WHERE id = ? AND tenant_id = ?",
            (memory_id, tenant_id),
        )
        row = cursor.fetchone()
        return row[0] if row else "private"

    # ── v4.0.0: 审计日志方法 ──────────────────────────────────────

    def record_provider_usage(
        self,
        tenant_id: str = ORG_ID,
        provider: str = "",
        model: str = "",
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        conn = self._get_conn()
        cursor = conn.cursor()
        now = get_local_now()
        cursor.execute(
            "INSERT INTO provider_usage (tenant_id, provider, model, tokens_in, tokens_out, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (tenant_id, provider, model, tokens_in, tokens_out, now),
        )
        conn.commit()

    def list_provider_usage(
        self,
        tenant_id: str = "",
        provider: str = "",
        limit: int = 100,
    ) -> tuple[list[dict], int]:
        conn = self._get_conn()
        cursor = conn.cursor()
        conditions: list[str] = []
        params: list = []
        if tenant_id:
            conditions.append("tenant_id = ?")
            params.append(tenant_id)
        if provider:
            conditions.append("provider = ?")
            params.append(provider)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        cursor.execute(f"SELECT COUNT(*) FROM provider_usage{where}", params)
        total = cursor.fetchone()[0]

        cursor.execute(
            f"SELECT id, tenant_id, provider, model, tokens_in, tokens_out, created_at "
            f"FROM provider_usage{where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        )
        rows = []
        for row in cursor.fetchall():
            rows.append({
                "id": row[0],
                "tenant_id": row[1],
                "provider": row[2],
                "model": row[3],
                "tokens_in": row[4],
                "tokens_out": row[5],
                "created_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
            })
        return rows, total

    def insert_evolution_event(
        self,
        *,
        event_id: str,
        tenant_id: str,
        user_id: str,
        source: str,
        signal: str,
        payload_json: str = "{}",
        weight: float = 1.0,
        created_at: str,
    ) -> None:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO evolution_events (id, tenant_id, user_id, source, signal, payload_json, weight, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, tenant_id, user_id, source, signal, payload_json, weight, created_at),
        )
        conn.commit()

    def list_evolution_events(self, tenant_id: str = ORG_ID, limit: int = 100) -> list:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tenant_id, user_id, source, signal, payload_json, weight, created_at
            FROM evolution_events WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?
            """,
            (tenant_id, limit),
        )
        return [
            {
                "id": r[0],
                "tenant_id": r[1],
                "user_id": r[2],
                "source": r[3],
                "signal": r[4],
                "payload_json": r[5],
                "weight": r[6],
                "created_at": r[7],
            }
            for r in cursor.fetchall()
        ]

    def count_evolution_events(self, tenant_id: str = ORG_ID, days: int = 7) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM evolution_events
            WHERE tenant_id = ? AND datetime(created_at) >= datetime('now', ?)
            """,
            (tenant_id, f"-{days} days"),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    def insert_evolution_apply_log(
        self,
        *,
        apply_id: str,
        tenant_id: str,
        target_type: str,
        target_path: str,
        before_hash: str,
        after_hash: str,
        before_content: str = "",
        diff_summary: str = "",
        status: str = "applied",
        created_at: str,
        batch_id: str | None = None,
    ) -> None:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO evolution_apply_log
            (id, tenant_id, target_type, target_path, before_hash, after_hash, before_content, diff_summary, status, created_at, batch_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                apply_id,
                tenant_id,
                target_type,
                target_path,
                before_hash,
                after_hash,
                before_content,
                diff_summary,
                status,
                created_at,
                batch_id,
            ),
        )
        conn.commit()

    def list_evolution_apply_logs_by_batch(self, batch_id: str) -> list:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tenant_id, target_type, target_path, before_hash, after_hash, before_content, diff_summary, status, created_at, batch_id
            FROM evolution_apply_log WHERE batch_id = ? ORDER BY created_at DESC
            """,
            (batch_id,),
        )
        rows = []
        for row in cursor.fetchall():
            rows.append({
                "id": row[0],
                "tenant_id": row[1],
                "target_type": row[2],
                "target_path": row[3],
                "before_hash": row[4],
                "after_hash": row[5],
                "before_content": row[6],
                "diff_summary": row[7],
                "status": row[8],
                "created_at": row[9],
                "batch_id": row[10] if len(row) > 10 else None,
            })
        return rows

    def count_insight_downvote_burst_metrics(
        self,
        tenant_id: str = ORG_ID,
        *,
        days: int = 7,
        min_count: int = 3,
    ) -> list[str]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT payload_json FROM evolution_events
            WHERE tenant_id = ? AND source = 'insight' AND signal = 'metric_downvote'
              AND created_at >= datetime('now', ?)
            """,
            (tenant_id, f"-{days} days"),
        )
        counts: dict[str, int] = {}
        import json as _json

        for (payload_json,) in cursor.fetchall():
            try:
                payload = _json.loads(payload_json or "{}")
            except (_json.JSONDecodeError, TypeError):
                continue
            metric_key = payload.get("metric_key") or "unknown"
            counts[metric_key] = counts.get(metric_key, 0) + 1
        return [key for key, count in counts.items() if count >= min_count]

    def get_evolution_apply_log(self, apply_id: str) -> Optional[dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tenant_id, target_type, target_path, before_hash, after_hash, before_content, diff_summary, status, created_at
            FROM evolution_apply_log WHERE id = ?
            """,
            (apply_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "tenant_id": row[1],
            "target_type": row[2],
            "target_path": row[3],
            "before_hash": row[4],
            "after_hash": row[5],
            "before_content": row[6] or "",
            "diff_summary": row[7] or "",
            "status": row[8],
            "created_at": row[9],
        }

