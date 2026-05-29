# TARS Transcription Repository
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


class TranscriptionRepo:
    """Transcription 域 Repository。"""

    def __init__(self, cm: ConnectionManager):
        self._cm = cm

    def _get_conn(self):
        return self._cm.get_conn()

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


