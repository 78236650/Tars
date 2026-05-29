# TARS Cron Repository
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


class CronRepo:
    """Cron 域 Repository。"""

    def __init__(self, cm: ConnectionManager):
        self._cm = cm

    def _get_conn(self):
        return self._cm.get_conn()

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
            created_at=_parse_db_datetime(row[8]),
            updated_at=_parse_db_datetime(row[9]),
            last_run=_parse_db_datetime(row[10]),
            next_run=_parse_db_datetime(row[11]),
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
            triggered_at=_parse_db_datetime(row[10]),
            read_at=_parse_db_datetime(row[11]),
            created_at=_parse_db_datetime(row[12]),
            updated_at=_parse_db_datetime(row[13]),
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


