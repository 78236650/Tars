# TARS Database Layer
# SQLite 会话、消息和记忆存储（门面 — CRUD 方法委托给各 repository）

import os
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from tars.database.models import (
    get_local_now, _parse_db_datetime,
    Session, Message, Memory, CronJob,
    ReminderNotification, Transcription, AuditLog, ApprovalRequest,
)
from tars.database.connection import ConnectionManager


class Database:
    """数据库门面。持有 ConnectionManager，CRUD 方法直接操作 SQLite。"""

    def __init__(self, db_path: Optional[str] = None):
        self._cm = ConnectionManager(db_path)
        self.db_path = self._cm.db_path

    def _get_conn(self):
        return self._cm.get_conn()

    def close(self):
        self._cm.close()

    def create_session(
        self,
        user_id: str = "default",
        title: str = "New Session",
        tenant_id: str = "default",
    ) -> Session:
        session_id = str(uuid.uuid4())
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sessions (id, agent_id, user_id, tenant_id, title, created_at, updated_at, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, "default", user_id, tenant_id, title, now, now, None),
        )
        conn.commit()

        return Session(
            id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            title=title,
            created_at=now,
            updated_at=now,
        )

    def get_session(self, session_id: str, tenant_id: str = "default") -> Optional[Session]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cols = {r[1] for r in cursor.execute("PRAGMA table_info(sessions)").fetchall()}
        if "metadata_json" in cols:
            cursor.execute(
                """
                SELECT id, agent_id, user_id, tenant_id, title, created_at, updated_at, summary, metadata_json
                FROM sessions
                WHERE id = ? AND tenant_id = ?
                """,
                (session_id, tenant_id),
            )
        else:
            cursor.execute(
                """
                SELECT id, agent_id, user_id, tenant_id, title, created_at, updated_at, summary
                FROM sessions
                WHERE id = ? AND tenant_id = ?
                """,
                (session_id, tenant_id),
            )
        row = cursor.fetchone()

        if row:
            meta = None
            if len(row) > 8 and row[8]:
                try:
                    meta = json.loads(row[8])
                except json.JSONDecodeError:
                    meta = {}
            return Session(
                id=row[0],
                agent_id=row[1],
                user_id=row[2],
                tenant_id=row[3],
                title=row[4],
                created_at=_parse_db_datetime(row[5]),
                updated_at=_parse_db_datetime(row[6]),
                summary=row[7],
                metadata_json=meta,
            )
        return None

    def get_session_metadata(self, session_id: str, tenant_id: str = "default") -> dict:
        session = self.get_session(session_id, tenant_id)
        if not session:
            return {}
        return dict(session.metadata_json or {})

    def set_session_metadata(
        self, session_id: str, tenant_id: str, metadata: dict
    ) -> None:
        conn = self._get_conn()
        cursor = conn.cursor()
        now = get_local_now()
        cursor.execute(
            """
            UPDATE sessions SET metadata_json = ?, updated_at = ?
            WHERE id = ? AND tenant_id = ?
            """,
            (json.dumps(metadata or {}, ensure_ascii=False), now, session_id, tenant_id),
        )
        conn.commit()

    def add_message(self, session_id: str, role: str, content: str) -> Message:
        message_id = str(uuid.uuid4())
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages VALUES (?, ?, ?, ?, ?)",
            (message_id, session_id, role, content, now)
        )

        cursor.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id)
        )
        conn.commit()

        return Message(id=message_id, session_id=session_id, role=role, content=content, timestamp=now)

    def get_messages(self, session_id: str) -> List[Message]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        )

        messages = []
        for row in cursor.fetchall():
            messages.append(Message(
                id=row[0],
                session_id=row[1],
                role=row[2],
                content=row[3],
                timestamp=_parse_db_datetime(row[4])
            ))

        return messages

    def list_sessions(
        self,
        user_id: str = "default",
        tenant_id: str = "default",
        limit: int = 50,
    ) -> List[Session]:
        """按 updated_at 倒序返回会话列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, agent_id, user_id, tenant_id, title, created_at, updated_at, summary
            FROM sessions
            WHERE user_id = ? AND tenant_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (user_id, tenant_id, limit),
        )
        sessions = []
        for row in cursor.fetchall():
            sessions.append(Session(
                id=row[0],
                agent_id=row[1],
                user_id=row[2],
                tenant_id=row[3],
                title=row[4],
                created_at=_parse_db_datetime(row[5]),
                updated_at=_parse_db_datetime(row[6]),
                summary=row[7],
            ))
        return sessions

    def delete_session(self, session_id: str, tenant_id: str = "default") -> bool:
        """删除会话及关联消息"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sessions WHERE id = ? AND tenant_id = ?", (session_id, tenant_id))
        if not cursor.fetchone():
            return False
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE id = ? AND tenant_id = ?", (session_id, tenant_id))
        conn.commit()
        return True

    def update_session_title(self, session_id: str, title: str, tenant_id: str = "default") -> bool:
        """更新会话标题"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sessions WHERE id = ? AND tenant_id = ?", (session_id, tenant_id))
        if not cursor.fetchone():
            return False
        now = get_local_now()
        cursor.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ? AND tenant_id = ?",
            (title, now, session_id, tenant_id),
        )
        conn.commit()
        return True

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
        tenant_id: str = "default",
        scope: str = "private",
    ) -> Memory:
        memory_id = str(uuid.uuid4())
        now = get_local_now()
        event_time_value = event_time or now.isoformat()
        entity_refs_json = json.dumps(entity_refs, ensure_ascii=False) if entity_refs is not None else None
        compressed_from_json = (
            json.dumps(compressed_from, ensure_ascii=False) if compressed_from is not None else None
        )

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memories
            (
                id, tenant_id, content, category, importance, created_at, updated_at,
                last_accessed, embedding, access_count, source, event_time, entity_refs,
                pinned, compressed_from, memory_type, scope
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                tenant_id,
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

        cursor.execute(
            "INSERT INTO memories_fts(rowid, content, category) VALUES (last_insert_rowid(), ?, ?)",
            (content, category)
        )

        conn.commit()

        return Memory(
            id=memory_id,
            content=content,
            category=category,
            tenant_id=tenant_id,
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
        )

    def get_memory(self, memory_id: str, tenant_id: str = "default") -> Optional[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id, tenant_id, content, category, importance, created_at, updated_at,
                last_accessed, source, pinned, compressed_from, memory_type, entity_refs, event_time, scope,
                promotion_group_id, kb_doc_id, kb_promotion_status
            FROM memories
            WHERE id = ? AND tenant_id = ?
            """,
            (memory_id, tenant_id),
        )
        return self._memory_from_row(cursor.fetchone())

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

    def search_memories(self, query: str, limit: int = 5, tenant_id: str = "default") -> List[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()

        # 转义 FTS5 特殊字符
        safe_query = query.replace('"', ' ').replace('*', ' ').replace('^', ' ')
        safe_query = safe_query.replace(':', ' ').replace('(', ' ').replace(')', ' ').replace('-', ' ').strip()
        has_cjk = self._has_cjk(query)

        memories = []
        # 1. 尝试 FTS5 搜索
        if safe_query:
            try:
                cursor.execute("""
                    SELECT m.id, m.tenant_id, m.content, m.category, m.importance, m.created_at, m.updated_at, m.last_accessed
                    FROM memories m
                    JOIN memories_fts fts ON m.rowid = fts.rowid
                    WHERE memories_fts MATCH ? AND (m.tenant_id = ? OR m.scope = 'shared')
                    ORDER BY rank
                    LIMIT ?
                """, (safe_query, tenant_id, limit))
                for row in cursor.fetchall():
                    memories.append(Memory(
                        id=row[0], tenant_id=row[1], content=row[2], category=row[3],
                        importance=row[4], created_at=datetime.fromisoformat(row[5]),
                        updated_at=datetime.fromisoformat(row[6]),
                        last_accessed=datetime.fromisoformat(row[7]) if row[7] else None,
                    ))
            except sqlite3.OperationalError:
                pass

        # 2. FTS5 无结果 + 含 CJK → LIKE fallback
        if not memories and has_cjk:
            try:
                cursor.execute("""
                    SELECT id, tenant_id, content, category, importance, created_at, updated_at, last_accessed
                    FROM memories WHERE (tenant_id = ? OR scope = 'shared') AND content LIKE ? ORDER BY importance DESC, updated_at DESC LIMIT ?
                """, (tenant_id, f"%{query}%", limit))
                for row in cursor.fetchall():
                    memories.append(Memory(
                        id=row[0], tenant_id=row[1], content=row[2], category=row[3],
                        importance=row[4], created_at=datetime.fromisoformat(row[5]),
                        updated_at=datetime.fromisoformat(row[6]),
                        last_accessed=datetime.fromisoformat(row[7]) if row[7] else None,
                    ))
            except sqlite3.OperationalError:
                pass

        # 3. 空结果兜底：通用 LIKE
        if not memories:
            try:
                cursor.execute("""
                    SELECT id, tenant_id, content, category, importance, created_at, updated_at, last_accessed
                    FROM memories WHERE (tenant_id = ? OR scope = 'shared') AND content LIKE ? ORDER BY importance DESC, updated_at DESC LIMIT ?
                """, (tenant_id, f"%{query}%", limit))
                for row in cursor.fetchall():
                    memories.append(Memory(
                        id=row[0], tenant_id=row[1], content=row[2], category=row[3],
                        importance=row[4], created_at=datetime.fromisoformat(row[5]),
                        updated_at=datetime.fromisoformat(row[6]),
                        last_accessed=datetime.fromisoformat(row[7]) if row[7] else None,
                    ))
            except sqlite3.OperationalError:
                pass

        for mem in memories:
            self._update_memory_access(mem.id)

        return memories

    def get_memories_by_category(self, category: str, limit: int = 10, tenant_id: str = "default") -> List[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, tenant_id, content, category, importance, created_at, updated_at, last_accessed
            FROM memories
            WHERE (tenant_id = ? OR scope = 'shared') AND category = ?
            ORDER BY importance DESC, updated_at DESC
            LIMIT ?
        """, (tenant_id, category, limit))

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

    def get_recent_memories(self, limit: int = 20, tenant_id: str = "default") -> List[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, tenant_id, content, category, importance, created_at, updated_at, last_accessed
            FROM memories
            WHERE tenant_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
        """, (tenant_id, limit))

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
        tenant_id: str = "default",
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

        cursor.execute("""
            UPDATE memories_fts
            SET content = ?, category = COALESCE(?, category)
            WHERE rowid = (SELECT rowid FROM memories WHERE id = ? AND tenant_id = ?)
        """, (content, category, memory_id, tenant_id))

        conn.commit()
        return cursor.rowcount > 0

    def reinforce_memory(self, memory_id: str, importance_delta: float = 0.02, tenant_id: str = "default"):
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

    def get_all_memories_with_metadata(self, tenant_id: str = "default"):
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

    def set_memory_pin(self, memory_id: str, pinned: bool, tenant_id: str = "default") -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE memories SET pinned = ?, updated_at = ? WHERE id = ? AND tenant_id = ?",
            (1 if pinned else 0, get_local_now(), memory_id, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def promote_memory(self, memory_id: str, tenant_id: str = "default") -> Optional[Memory]:
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
        return self.get_memory(memory_id, tenant_id=tenant_id)

    def set_memory_promotion_meta(
        self,
        memory_id: str,
        *,
        tenant_id: str = "default",
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

    def delete_memory(self, memory_id: str, tenant_id: str = "default"):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT rowid FROM memories WHERE id = ? AND tenant_id = ?", (memory_id, tenant_id))
        row = cursor.fetchone()
        if row:
            cursor.execute("DELETE FROM memories_fts WHERE rowid = ?", (row[0],))
        cursor.execute("DELETE FROM memories WHERE id = ? AND tenant_id = ?", (memory_id, tenant_id))
        conn.commit()
        return cursor.rowcount > 0

    def get_memory_stats(self, tenant_id: str = "default") -> Dict[str, Any]:
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
        tenant_id: str = "default",
    ) -> Tuple[List[Memory], int]:
        conn = self._get_conn()
        cursor = conn.cursor()
        time_expr = "julianday(replace(substr(created_at, 1, 19), 'T', ' '))"
        clauses = [
            "tenant_id = ?",
            "memory_type = 'episodic'",
            f"{time_expr} >= julianday('now', '-7 day')",
        ]
        params: List[Any] = [tenant_id]
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

    def list_longterm_memories(self, tenant_id: str = "default", page: int = 1, page_size: int = 20) -> Tuple[List[Memory], int]:
        conn = self._get_conn()
        cursor = conn.cursor()
        where = "tenant_id = ? AND (importance >= 0.6 OR pinned = 1 OR memory_type = 'longterm')"
        cursor.execute(f"SELECT COUNT(*) FROM memories WHERE {where}", (tenant_id,))
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
            (tenant_id, page_size, offset),
        )
        return [self._memory_from_row(row) for row in cursor.fetchall()], total

    def list_all_memories(
        self,
        page: int = 1,
        page_size: int = 20,
        query: str = "",
        category: str = "",
        memory_type: str = "",
        tenant_id: str = "default",
    ) -> Tuple[List[Memory], int]:
        conn = self._get_conn()
        cursor = conn.cursor()
        clauses = ["tenant_id = ?"]
        params: List[Any] = [tenant_id]
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

    def list_memories_for_tree(self, tenant_id: str = "default", limit: int = 5000) -> List[Memory]:
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
        if deleted > 0:
            # 重建 FTS 索引
            cursor.execute("DELETE FROM memories_fts")
            cursor.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
        conn.commit()
        return deleted

    def forget_core_line(self, block: str, line_contains: str, tenant_id: str = "default") -> bool:
        """从 core memory 区块中删除匹配的行"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM core_memory_blocks WHERE name = ? AND tenant_id = ?",
            (block, tenant_id),
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
            "UPDATE core_memory_blocks SET content = ?, updated_at = ? WHERE name = ? AND tenant_id = ?",
            (new_content, now, block, tenant_id),
        )
        conn.commit()
        return True

    def get_document_file(self, doc_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, collection_id, file_name, file_path, file_type, chunk_count, status, "
            "doc_type, profile_ready, one_liner, status_message, created_at "
            "FROM document_files WHERE id = ?",
            (doc_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "collection_id": row[1],
            "file_name": row[2],
            "file_path": row[3],
            "file_type": row[4],
            "chunk_count": row[5],
            "status": row[6],
            "doc_type": row[7] or "generic",
            "profile_ready": bool(row[8]),
            "one_liner": row[9],
            "status_message": row[10],
            "created_at": row[11],
        }

    def update_document_file(self, doc_id: str, **fields: Any) -> bool:
        """部分更新 document_files 行；仅允许已知列。"""
        allowed = {
            "status",
            "chunk_count",
            "doc_type",
            "profile_ready",
            "one_liner",
            "status_message",
            "file_type",
        }
        sets: List[str] = []
        values: List[Any] = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == "profile_ready":
                value = 1 if bool(value) else 0
            sets.append(f"{key} = ?")
            values.append(value)
        if not sets:
            return False
        values.append(doc_id)
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE document_files SET {', '.join(sets)} WHERE id = ?",
            values,
        )
        conn.commit()
        return cursor.rowcount > 0

    def delete_document_file(self, doc_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM document_files WHERE id = ?", (doc_id,))
        conn.commit()
        return cursor.rowcount > 0

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
    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value)

    def _row_to_cronjob(self, row) -> CronJob:
        return CronJob(
            id=row[0],
            user_id=row[1],
            name=row[2],
            description=row[3],
            cron_expression=row[4],
            task_type=row[5],
            task_config=row[6],
            enabled=bool(row[7]),
            created_at=self._parse_datetime(row[8]),
            updated_at=self._parse_datetime(row[9]),
            last_run=self._parse_datetime(row[10]),
            next_run=self._parse_datetime(row[11]),
        )

    def _row_to_reminder_notification(self, row) -> ReminderNotification:
        return ReminderNotification(
            id=row[0],
            user_id=row[1],
            job_id=row[2],
            session_id=row[3],
            task_name=row[4],
            message=row[5],
            delivery_status=row[6],
            error_message=row[7],
            summary_logs=json.loads(row[8] or "[]"),
            is_read=bool(row[9]),
            triggered_at=self._parse_datetime(row[10]),
            read_at=self._parse_datetime(row[11]),
            created_at=self._parse_datetime(row[12]),
            updated_at=self._parse_datetime(row[13]),
        )

    def create_cronjob(
        self,
        user_id: str,
        name: str,
        cron_expression: str,
        task_type: str,
        task_config: str,
        description: Optional[str] = None
    ) -> CronJob:
        cronjob_id = str(uuid.uuid4())
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cronjobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cronjob_id, user_id, name, description, cron_expression,
            task_type, task_config, 1, now, now, None, None
        ))
        conn.commit()

        return CronJob(
            id=cronjob_id,
            user_id=user_id,
            name=name,
            description=description,
            cron_expression=cron_expression,
            task_type=task_type,
            task_config=task_config,
            enabled=True,
            created_at=now,
            updated_at=now
        )

    def get_cronjob(self, cronjob_id: str) -> Optional[CronJob]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cronjobs WHERE id = ?", (cronjob_id,))
        row = cursor.fetchone()

        if row:
            return self._row_to_cronjob(row)
        return None

    def get_user_cronjobs(self, user_id: str) -> List[CronJob]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM cronjobs WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )

        cronjobs = []
        for row in cursor.fetchall():
            cronjobs.append(self._row_to_cronjob(row))
        return cronjobs

    def get_enabled_cronjobs(self) -> List[CronJob]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cronjobs WHERE enabled = 1")

        cronjobs = []
        for row in cursor.fetchall():
            cronjobs.append(self._row_to_cronjob(row))
        return cronjobs

    def update_cronjob(self, cronjob_id: str, **kwargs):
        now = get_local_now()
        conn = self._get_conn()
        cursor = conn.cursor()

        updates = []
        params = []

        for key, value in kwargs.items():
            if key in ['name', 'description', 'cron_expression', 'task_type', 'task_config']:
                updates.append(f"{key} = ?")
                params.append(value)
            elif key == 'enabled':
                updates.append("enabled = ?")
                params.append(1 if value else 0)
            elif key == 'last_run':
                updates.append("last_run = ?")
                params.append(value.isoformat() if value else None)
            elif key == 'next_run':
                updates.append("next_run = ?")
                params.append(value.isoformat() if value else None)

        if updates:
            updates.append("updated_at = ?")
            params.append(now.isoformat())
            params.append(cronjob_id)
            cursor.execute(f"UPDATE cronjobs SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

    def delete_cronjob(self, cronjob_id: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reminder_notifications WHERE job_id = ?", (cronjob_id,))
        cursor.execute("DELETE FROM cronjobs WHERE id = ?", (cronjob_id,))
        conn.commit()

    def create_reminder_notification(
        self,
        user_id: str,
        job_id: str,
        session_id: Optional[str],
        task_name: str,
        message: str,
        delivery_status: str,
        error_message: Optional[str] = None,
        summary_logs: Optional[List[Dict[str, Any]]] = None,
        triggered_at: Optional[datetime] = None,
    ) -> ReminderNotification:
        notification_id = str(uuid.uuid4())
        now = get_local_now()
        triggered = triggered_at or now

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO reminder_notifications (
                id, user_id, job_id, session_id, task_name, message, delivery_status,
                error_message, summary_logs, is_read, triggered_at, read_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                notification_id,
                user_id,
                job_id,
                session_id,
                task_name,
                message,
                delivery_status,
                error_message,
                json.dumps(summary_logs or [], ensure_ascii=False),
                0,
                triggered.isoformat(),
                None,
                now.isoformat(),
                now.isoformat(),
            ),
        )
        conn.commit()

        return ReminderNotification(
            id=notification_id,
            user_id=user_id,
            job_id=job_id,
            session_id=session_id,
            task_name=task_name,
            message=message,
            delivery_status=delivery_status,
            error_message=error_message,
            summary_logs=summary_logs or [],
            is_read=False,
            triggered_at=triggered,
            read_at=None,
            created_at=now,
            updated_at=now,
        )

    def list_reminder_notifications(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[ReminderNotification]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM reminder_notifications
            WHERE user_id = ?
            ORDER BY triggered_at DESC, created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        )
        return [self._row_to_reminder_notification(row) for row in cursor.fetchall()]

    def count_reminder_notifications(self, user_id: str) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM reminder_notifications WHERE user_id = ?",
            (user_id,),
        )
        return int(cursor.fetchone()[0])

    def count_unread_reminder_notifications(self, user_id: str) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM reminder_notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
        )
        return int(cursor.fetchone()[0])

    def get_reminder_notification(self, notification_id: str) -> Optional[ReminderNotification]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM reminder_notifications WHERE id = ?",
            (notification_id,),
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_reminder_notification(row)
        return None

    def mark_reminder_notification_read(self, notification_id: str) -> Optional[ReminderNotification]:
        notification = self.get_reminder_notification(notification_id)
        if not notification:
            return None
        if notification.is_read:
            return notification

        now = get_local_now().isoformat()
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE reminder_notifications
            SET is_read = 1, read_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, notification_id),
        )
        conn.commit()
        return self.get_reminder_notification(notification_id)

    def get_latest_reminder_notification_for_job(
        self,
        job_id: str,
    ) -> Optional[ReminderNotification]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM reminder_notifications
            WHERE job_id = ?
            ORDER BY triggered_at DESC, created_at DESC
            LIMIT 1
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_reminder_notification(row)
        return None

    # ============ v2.2 Working Context ============

    def get_working_context(self, session_id: str, tenant_id: str = "default") -> dict:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM working_contexts WHERE tenant_id = ? AND session_id = ?",
            (tenant_id, session_id),
        )
        row = cur.fetchone()
        if not row:
            return {}
        import json
        return {
            "tenant_id": row[0],
            "session_id": row[1],
            "focus_entities": json.loads(row[2] or "[]"),
            "current_intent": row[3] or "unknown",
            "intent_confidence": row[4] or 0,
            "open_threads": json.loads(row[5] or "[]"),
            "active_skills": json.loads(row[6] or "[]"),
            "last_scene_snapshot": json.loads(row[7] or "{}"),
            "updated_at": row[8],
        }

    def upsert_working_context(self, session_id: str, tenant_id: str = "default", **kwargs):
        conn = self._get_conn()
        cur = conn.cursor()
        import json
        now = get_local_now().isoformat()
        cur.execute(
            "SELECT session_id FROM working_contexts WHERE tenant_id = ? AND session_id = ?",
            (tenant_id, session_id),
        )
        exists = cur.fetchone()
        if exists:
            sets = []
            vals = []
            for k in ["focus_entities", "current_intent", "intent_confidence",
                       "open_threads", "active_skills", "last_scene_snapshot"]:
                if k in kwargs:
                    v = kwargs[k]
                    sets.append(f"{k} = ?")
                    vals.append(json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
            sets.append("updated_at = ?"); vals.append(now)
            vals.extend([tenant_id, session_id])
            cur.execute(
                f"UPDATE working_contexts SET {', '.join(sets)} WHERE tenant_id = ? AND session_id = ?",
                vals,
            )
        else:
            cur.execute(
                "INSERT INTO working_contexts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (tenant_id, session_id,
                 json.dumps(kwargs.get("focus_entities", []), ensure_ascii=False),
                 kwargs.get("current_intent", "unknown"),
                 kwargs.get("intent_confidence", 0),
                 json.dumps(kwargs.get("open_threads", []), ensure_ascii=False),
                 json.dumps(kwargs.get("active_skills", []), ensure_ascii=False),
                 json.dumps(kwargs.get("last_scene_snapshot", {}), ensure_ascii=False),
                 now),
            )
        conn.commit()

    def cleanup_working_contexts(self, max_age_hours: int = 72, tenant_id: str | None = None):
        conn = self._get_conn()
        cur = conn.cursor()
        cutoff = (get_local_now() - timedelta(hours=max_age_hours)).isoformat()
        if tenant_id is None:
            cur.execute("DELETE FROM working_contexts WHERE updated_at < ?", (cutoff,))
        else:
            cur.execute(
                "DELETE FROM working_contexts WHERE tenant_id = ? AND updated_at < ?",
                (tenant_id, cutoff),
            )
        conn.commit()

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

    def create_transcription(
        self,
        user_id: str,
        file_path: str,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        language: Optional[str] = None,
        model_used: Optional[str] = None,
        transcription_id: Optional[str] = None,
    ) -> Transcription:
        transcription_id = transcription_id or str(uuid.uuid4())
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO transcriptions
            (id, user_id, file_path, file_name, file_size, language, status, model_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (transcription_id, user_id, file_path, file_name, file_size, language, "pending", model_used, now),
        )
        conn.commit()

        return Transcription(
            id=transcription_id,
            user_id=user_id,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            language=language,
            status="pending",
            model_used=model_used,
            created_at=now,
        )

    def get_transcription(self, transcription_id: str) -> Optional[Transcription]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, file_path, file_name, file_size, duration, language, status,
                   transcript, segments, summary, summary_type, key_points, model_used,
                   created_at, completed_at, error_message
            FROM transcriptions WHERE id = ?
            """,
            (transcription_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_transcription(row)

    def list_transcriptions(self, user_id: str = "default", limit: int = 50, offset: int = 0) -> List[Transcription]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, file_path, file_name, file_size, duration, language, status,
                   transcript, segments, summary, summary_type, key_points, model_used,
                   created_at, completed_at, error_message
            FROM transcriptions WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        )
        return [self._row_to_transcription(row) for row in cursor.fetchall()]

    def update_transcription(self, transcription_id: str, **kwargs) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()

        allowed_fields = {
            "duration", "language", "status", "transcript", "segments",
            "summary", "summary_type", "key_points", "model_used", "error_message",
            "file_path", "file_name", "file_size",
        }
        updates = []
        params = []

        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = ?")
                params.append(value)

        if not updates:
            return False

        now = get_local_now()
        updates.append("completed_at = ?")
        params.append(now)
        params.append(transcription_id)

        cursor.execute(
            f"UPDATE transcriptions SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
        return cursor.rowcount > 0

    def delete_transcription(self, transcription_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()

        # 先获取文件路径用于删除文件
        cursor.execute("SELECT file_path FROM transcriptions WHERE id = ?", (transcription_id,))
        row = cursor.fetchone()
        if not row:
            return False

        file_path = row[0]
        cursor.execute("DELETE FROM transcriptions WHERE id = ?", (transcription_id,))
        conn.commit()

        # 尝试删除关联文件
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

        return True

    # ── v4.0.0: scope 管理 ────────────────────────────────────

    def set_memory_scope(self, memory_id: str, scope: str, tenant_id: str = "default") -> bool:
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
            """
            SELECT
                id, tenant_id, content, category, importance, created_at, updated_at,
                last_accessed, source, pinned, compressed_from, memory_type, entity_refs, event_time, scope
            FROM memories WHERE id = ?
            """,
            (memory_id,),
        )
        row = cursor.fetchone()
        return self._memory_from_row(row)

    def get_memory_scope(self, memory_id: str, tenant_id: str = "default") -> str:
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

    def add_audit_log(
        self,
        action: str,
        resource_type: str,
        tenant_id: str = "default",
        user_id: str = "default",
        resource_id: str = "",
        detail: str = "",
        client_ip: str = "",
    ) -> Optional[AuditLog]:
        conn = self._get_conn()
        cursor = conn.cursor()
        log_id = str(uuid.uuid4())
        now = get_local_now()
        cursor.execute(
            "INSERT INTO audit_logs (id, tenant_id, user_id, action, resource_type, resource_id, detail, client_ip, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (log_id, tenant_id, user_id, action, resource_type, resource_id, detail, client_ip, now),
        )
        conn.commit()
        return AuditLog(
            id=log_id,
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
            client_ip=client_ip,
            created_at=now,
        )

    def create_approval_request(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
        tool_name: str,
        arguments: str,
    ) -> ApprovalRequest:
        conn = self._get_conn()
        cursor = conn.cursor()
        request_id = str(uuid.uuid4())
        now = get_local_now()
        cursor.execute(
            """
            INSERT INTO approval_requests
            (id, tenant_id, user_id, session_id, tool_name, arguments, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (request_id, tenant_id, user_id, session_id, tool_name, arguments, now),
        )
        conn.commit()
        return ApprovalRequest(
            id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            status="pending",
            created_at=now,
        )

    def get_approval_request(self, request_id: str) -> Optional[ApprovalRequest]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tenant_id, user_id, session_id, tool_name, arguments, status,
                   created_at, resolved_at, resolved_by
            FROM approval_requests WHERE id = ?
            """,
            (request_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return ApprovalRequest(
            id=row[0],
            tenant_id=row[1],
            user_id=row[2],
            session_id=row[3],
            tool_name=row[4],
            arguments=row[5],
            status=row[6],
            created_at=row[7],
            resolved_at=row[8],
            resolved_by=row[9] or "",
        )

    def update_approval_request(
        self,
        request_id: str,
        *,
        status: str,
        resolved_by: str = "",
    ) -> Optional[ApprovalRequest]:
        conn = self._get_conn()
        cursor = conn.cursor()
        now = get_local_now()
        cursor.execute(
            """
            UPDATE approval_requests
            SET status = ?, resolved_at = ?, resolved_by = ?
            WHERE id = ? AND status = 'pending'
            """,
            (status, now, resolved_by, request_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
        return self.get_approval_request(request_id)

    def list_pending_approval_requests(
        self,
        *,
        session_id: str = "",
        tenant_id: str = "",
    ) -> list[ApprovalRequest]:
        conn = self._get_conn()
        cursor = conn.cursor()
        conditions = ["status = 'pending'"]
        params: list = []
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if tenant_id:
            conditions.append("tenant_id = ?")
            params.append(tenant_id)
        where = " AND ".join(conditions)
        cursor.execute(
            f"""
            SELECT id, tenant_id, user_id, session_id, tool_name, arguments, status,
                   created_at, resolved_at, resolved_by
            FROM approval_requests WHERE {where}
            ORDER BY created_at DESC
            """,
            params,
        )
        rows = cursor.fetchall()
        return [
            ApprovalRequest(
                id=row[0],
                tenant_id=row[1],
                user_id=row[2],
                session_id=row[3],
                tool_name=row[4],
                arguments=row[5],
                status=row[6],
                created_at=row[7],
                resolved_at=row[8],
                resolved_by=row[9] or "",
            )
            for row in rows
        ]

    def list_audit_logs(
        self,
        tenant_id: str = "",
        user_id: str = "",
        action: str = "",
        actions: Optional[list[str]] = None,
        resource_type: str = "",
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLog], int]:
        conn = self._get_conn()
        cursor = conn.cursor()
        conditions: list[str] = []
        params: list = []
        if tenant_id:
            conditions.append("tenant_id = ?")
            params.append(tenant_id)
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if actions:
            placeholders = ",".join("?" * len(actions))
            conditions.append(f"action IN ({placeholders})")
            params.extend(actions)
        elif action:
            conditions.append("action = ?")
            params.append(action)
        if resource_type:
            conditions.append("resource_type = ?")
            params.append(resource_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        # total
        cursor.execute(f"SELECT COUNT(*) FROM audit_logs{where}", params)
        total = cursor.fetchone()[0]

        # page
        offset = (page - 1) * page_size
        cursor.execute(
            f"SELECT id, tenant_id, user_id, action, resource_type, resource_id, detail, client_ip, created_at "
            f"FROM audit_logs{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        )
        return [self._row_to_audit_log(row) for row in cursor.fetchall()], total

    def _row_to_audit_log(self, row) -> AuditLog:
        return AuditLog(
            id=row[0],
            tenant_id=row[1],
            user_id=row[2],
            action=row[3],
            resource_type=row[4],
            resource_id=row[5],
            detail=row[6],
            client_ip=row[7],
            created_at=_parse_db_datetime(row[8]),
        )

    def record_provider_usage(
        self,
        tenant_id: str = "default",
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

    def _row_to_transcription(self, row) -> Transcription:
        return Transcription(
            id=row[0],
            user_id=row[1],
            file_path=row[2],
            file_name=row[3],
            file_size=row[4],
            duration=row[5],
            language=row[6],
            status=row[7],
            transcript=row[8],
            segments=row[9],
            summary=row[10],
            summary_type=row[11],
            key_points=row[12],
            model_used=row[13],
            created_at=_parse_db_datetime(row[14]),
            completed_at=_parse_db_datetime(row[15]),
            error_message=row[16],
            approved_at=row[17] if len(row) > 17 else None,
            knowledge_doc_id=row[18] if len(row) > 18 else None,
        )

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

    def list_evolution_events(self, tenant_id: str = "default", limit: int = 100) -> list:
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

    def count_evolution_events(self, tenant_id: str = "default", days: int = 7) -> int:
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
        tenant_id: str = "default",
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
