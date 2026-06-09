# TARS Session Repository
# Auto-extracted from base.py

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from tars.database.models import (
    get_local_now, _parse_db_datetime,
    Session, Message, Memory, CronJob,
    ReminderNotification, Transcription, AuditLog, ApprovalRequest,
)
from tars.database.connection import ConnectionManager
from tars.org import ORG_ID


class SessionRepo:
    """Session 域 Repository。"""

    def __init__(self, cm: ConnectionManager):
        self._cm = cm

    @staticmethod
    def _resolve_user_id(user_id: Optional[str] = None) -> str:
        if user_id is not None:
            return user_id
        try:
            from tars.context import get_current_user_id
            return get_current_user_id()
        except RuntimeError:
            return "default"

    def _get_conn(self):
        return self._cm.get_conn()

    def _has_column(self, table: str, column: str) -> bool:
        """Check if a column exists — dialect-aware (Postgres vs SQLite)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        if self._cm.dialect == "postgres":
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s AND column_name = %s",
                (table, column),
            )
            return cursor.fetchone() is not None
        # SQLite
        cols = {r[1] for r in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
        return column in cols

    def create_session(
        self,
        user_id: str = "default",
        title: str = "New Session",
        tenant_id: str = ORG_ID,
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

    def get_session(
        self,
        session_id: str,
        tenant_id: str = ORG_ID,
        user_id: Optional[str] = None,
    ) -> Optional[Session]:
        resolved_user_id = self._resolve_user_id(user_id)
        conn = self._get_conn()
        cursor = conn.cursor()
        if self._has_column("sessions", "metadata_json"):
            cursor.execute(
                """
                SELECT id, agent_id, user_id, tenant_id, title, created_at, updated_at, summary, metadata_json
                FROM sessions
                WHERE id = ? AND tenant_id = ? AND user_id = ?
                """,
                (session_id, tenant_id, resolved_user_id),
            )
        else:
            cursor.execute(
                """
                SELECT id, agent_id, user_id, tenant_id, title, created_at, updated_at, summary
                FROM sessions
                WHERE id = ? AND tenant_id = ? AND user_id = ?
                """,
                (session_id, tenant_id, resolved_user_id),
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

    def get_session_metadata(
        self,
        session_id: str,
        tenant_id: str = ORG_ID,
        user_id: Optional[str] = None,
    ) -> dict:
        session = self.get_session(session_id, tenant_id, user_id=user_id)
        if not session:
            return {}
        return dict(session.metadata_json or {})

    def set_session_metadata(
        self,
        session_id: str,
        tenant_id: str,
        metadata: dict,
        user_id: Optional[str] = None,
    ) -> None:
        resolved_user_id = self._resolve_user_id(user_id)
        conn = self._get_conn()
        cursor = conn.cursor()
        now = get_local_now()
        cursor.execute(
            """
            UPDATE sessions SET metadata_json = ?, updated_at = ?
            WHERE id = ? AND tenant_id = ? AND user_id = ?
            """,
            (
                json.dumps(metadata or {}, ensure_ascii=False),
                now,
                session_id,
                tenant_id,
                resolved_user_id,
            ),
        )
        conn.commit()

    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[dict] = None) -> Message:
        message_id = str(uuid.uuid4())
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()
        # 检查是否有 metadata_json 列
        if self._has_column("messages", "metadata_json"):
            metadata_json_str = json.dumps(metadata, ensure_ascii=False) if metadata else None
            cursor.execute(
                "INSERT INTO messages (id, session_id, role, content, timestamp, metadata_json) VALUES (?, ?, ?, ?, ?, ?)",
                (message_id, session_id, role, content, now, metadata_json_str),
            )
        else:
            cursor.execute(
                "INSERT INTO messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                (message_id, session_id, role, content, now),
            )

        cursor.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id)
        )
        conn.commit()

        return Message(id=message_id, session_id=session_id, role=role, content=content, timestamp=now, metadata_json=metadata)

    def get_messages(self, session_id: str) -> List[Message]:
        conn = self._get_conn()
        cursor = conn.cursor()
        # 检查是否有 metadata_json 列
        if self._has_column("messages", "metadata_json"):
            cursor.execute(
                "SELECT id, session_id, role, content, timestamp, metadata_json FROM messages WHERE session_id = ? ORDER BY timestamp",
                (session_id,)
            )
        else:
            cursor.execute(
                "SELECT id, session_id, role, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp",
                (session_id,)
            )

        messages = []
        for row in cursor.fetchall():
            meta = None
            if len(row) > 5 and row[5]:
                try:
                    meta = json.loads(row[5])
                except json.JSONDecodeError:
                    meta = {}
            messages.append(Message(
                id=row[0],
                session_id=row[1],
                role=row[2],
                content=row[3],
                timestamp=_parse_db_datetime(row[4]),
                metadata_json=meta
            ))

        return messages

    def list_sessions(
        self,
        user_id: Optional[str] = None,
        tenant_id: str = ORG_ID,
        limit: int = 50,
    ) -> List[Session]:
        resolved_user_id = self._resolve_user_id(user_id)
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
            (resolved_user_id, tenant_id, limit),
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

    def delete_session(
        self,
        session_id: str,
        tenant_id: str = ORG_ID,
        user_id: Optional[str] = None,
    ) -> bool:
        """删除会话及关联消息"""
        resolved_user_id = self._resolve_user_id(user_id)
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM sessions WHERE id = ? AND tenant_id = ? AND user_id = ?",
            (session_id, tenant_id, resolved_user_id),
        )
        if not cursor.fetchone():
            return False
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute(
            "DELETE FROM sessions WHERE id = ? AND tenant_id = ? AND user_id = ?",
            (session_id, tenant_id, resolved_user_id),
        )
        conn.commit()
        return True

    def update_session_title(
        self,
        session_id: str,
        title: str,
        tenant_id: str = ORG_ID,
        user_id: Optional[str] = None,
    ) -> bool:
        """更新会话标题"""
        resolved_user_id = self._resolve_user_id(user_id)
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM sessions WHERE id = ? AND tenant_id = ? AND user_id = ?",
            (session_id, tenant_id, resolved_user_id),
        )
        if not cursor.fetchone():
            return False
        now = get_local_now()
        cursor.execute(
            """
            UPDATE sessions SET title = ?, updated_at = ?
            WHERE id = ? AND tenant_id = ? AND user_id = ?
            """,
            (title, now, session_id, tenant_id, resolved_user_id),
        )
        conn.commit()
        return True

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
        expected_status: str = "pending",
    ) -> Optional[ApprovalRequest]:
        """更新审批请求状态。

        默认仅允许从 pending 转出(防并发双重处理)。v5.0.5/A2 宽限窗口的
        迟到决策需从 timeout 转出,故 expected_status 可显式指定。
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now = get_local_now()
        cursor.execute(
            """
            UPDATE approval_requests
            SET status = ?, resolved_at = ?, resolved_by = ?
            WHERE id = ? AND status = ?
            """,
            (status, now, resolved_by, request_id, expected_status),
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


