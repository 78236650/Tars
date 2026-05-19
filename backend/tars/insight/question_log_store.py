"""InsightForge question log for few-shot recall (INS-2.0)."""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..database.base import Database, get_local_now


def _estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


class InsightQuestionLogStore:
    def __init__(self, db: Database):
        self.db = db

    def _now(self) -> str:
        return get_local_now().isoformat()

    def insert_log(
        self,
        *,
        datasource_id: str,
        tenant_id: str,
        question: str,
        sql: str,
        branch: str,
        outcome: str,
        caliber_tier: str,
        user_id: str,
        metric_key: Optional[str] = None,
        feedback: Optional[int] = None,
    ) -> str:
        log_id = str(uuid.uuid4())
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO insight_question_log (
                id, datasource_id, tenant_id, question, question_embedding,
                metric_key, sql, branch, outcome, feedback, caliber_tier, user_id, created_at
            ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                datasource_id,
                tenant_id,
                question,
                metric_key,
                sql,
                branch,
                outcome,
                feedback,
                caliber_tier,
                user_id,
                self._now(),
            ),
        )
        conn.commit()
        return log_id

    def list_fewshot_candidates(
        self,
        datasource_id: str,
        tenant_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT question, sql, metric_key, branch, outcome, feedback
            FROM insight_question_log
            WHERE datasource_id = ? AND tenant_id = ?
              AND outcome = 'success'
              AND (feedback IS NULL OR feedback >= 0)
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (datasource_id, tenant_id, limit),
        )
        rows = cursor.fetchall()
        return [
            {
                "question": r[0],
                "sql": r[1],
                "metric_key": r[2],
                "branch": r[3],
            }
            for r in rows
        ]

    def select_for_prompt(
        self,
        candidates: List[Dict[str, Any]],
        *,
        max_items: int = 5,
        max_tokens: int = 2000,
        recall_timeout_ms: int = 200,
    ) -> List[Dict[str, Any]]:
        """H4: cap few-shot items/tokens; skip if recall budget exceeded."""
        started = time.perf_counter()
        selected: List[Dict[str, Any]] = []
        used_tokens = 0
        for item in candidates:
            if (time.perf_counter() - started) * 1000 > recall_timeout_ms:
                return []
            if len(selected) >= max_items:
                break
            block = json.dumps(item, ensure_ascii=False)
            tok = _estimate_tokens(block)
            if used_tokens + tok > max_tokens:
                break
            selected.append(item)
            used_tokens += tok
        return selected

    def get_log(self, log_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, datasource_id, tenant_id, question, metric_key, sql, branch,
                   outcome, feedback, caliber_tier, user_id, created_at
            FROM insight_question_log
            WHERE id = ? AND tenant_id = ?
            """,
            (log_id, tenant_id),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "datasource_id": row[1],
            "tenant_id": row[2],
            "question": row[3],
            "metric_key": row[4],
            "sql": row[5],
            "branch": row[6],
            "outcome": row[7],
            "feedback": row[8],
            "caliber_tier": row[9],
            "user_id": row[10],
            "created_at": row[11],
        }

    def feedback_stats_for_metric(
        self,
        datasource_id: str,
        tenant_id: str,
        metric_key: str,
        window_days: int,
    ) -> Dict[str, int]:
        try:
            now_dt = datetime.fromisoformat(self._now().replace("Z", "+00:00"))
        except ValueError:
            now_dt = datetime.utcnow()
        since = (now_dt - timedelta(days=window_days)).isoformat()
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
              SUM(CASE WHEN feedback < 0 THEN 1 ELSE 0 END),
              SUM(CASE WHEN feedback > 0 THEN 1 ELSE 0 END)
            FROM insight_question_log
            WHERE datasource_id = ? AND tenant_id = ? AND metric_key = ?
              AND feedback IS NOT NULL AND created_at >= ?
            """,
            (datasource_id, tenant_id, metric_key, since),
        )
        row = cursor.fetchone()
        down = int(row[0] or 0) if row else 0
        up = int(row[1] or 0) if row else 0
        return {"down": down, "up": up}

    def update_feedback(self, log_id: str, tenant_id: str, feedback: int) -> bool:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE insight_question_log
            SET feedback = ?
            WHERE id = ? AND tenant_id = ?
            """,
            (feedback, log_id, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0
