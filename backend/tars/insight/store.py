"""InsightForge persistence (profile runs + metrics)."""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from ..database.base import Database, get_local_now
from .models import InsightMetric, InsightProfileRun


class InsightProfileRunStore:
    def __init__(self, db: Database):
        self.db = db

    def _now(self) -> str:
        return get_local_now().isoformat()

    def create(
        self,
        datasource_id: str,
        tenant_id: str,
        capability_version: str,
        budget: Dict[str, Any],
    ) -> InsightProfileRun:
        run_id = str(uuid.uuid4())
        now = self._now()
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO insight_profile_runs (
                id, datasource_id, tenant_id, capability_version, status,
                budget_json, progress_json, created_at
            ) VALUES (?, ?, ?, ?, 'pending', ?, '{}', ?)
            """,
            (
                run_id,
                datasource_id,
                tenant_id,
                capability_version,
                json.dumps(budget, ensure_ascii=False),
                now,
            ),
        )
        conn.commit()
        return self.get(run_id, tenant_id)  # type: ignore

    def get(self, run_id: str, tenant_id: str = "default") -> Optional[InsightProfileRun]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM insight_profile_runs WHERE id = ? AND tenant_id = ?",
            (run_id, tenant_id),
        )
        return self._row_to_run(cursor.fetchone())

    def list_by_datasource(
        self, datasource_id: str, tenant_id: str = "default", limit: int = 20
    ) -> List[InsightProfileRun]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM insight_profile_runs
            WHERE datasource_id = ? AND tenant_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (datasource_id, tenant_id, limit),
        )
        return [r for row in cursor.fetchall() if (r := self._row_to_run(row))]

    def update_progress(
        self,
        run_id: str,
        tenant_id: str,
        progress: Dict[str, Any],
        status: Optional[str] = None,
    ) -> None:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        now = self._now()
        if status:
            cursor.execute(
                """
                UPDATE insight_profile_runs
                SET progress_json = ?, status = ?,
                    started_at = COALESCE(started_at, ?)
                WHERE id = ? AND tenant_id = ?
                """,
                (
                    json.dumps(progress, ensure_ascii=False),
                    status,
                    now if status == "running" else None,
                    run_id,
                    tenant_id,
                ),
            )
        else:
            cursor.execute(
                """
                UPDATE insight_profile_runs
                SET progress_json = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (json.dumps(progress, ensure_ascii=False), run_id, tenant_id),
            )
        conn.commit()

    def sweep_stuck_runs(self, reason: str = "process restarted") -> int:
        """On startup: mark any pending/running runs as failed."""
        now = self._now()
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE insight_profile_runs
            SET status = 'failed', error = ?, finished_at = ?
            WHERE status IN ('pending', 'running')
            """,
            (reason, now),
        )
        conn.commit()
        return cursor.rowcount or 0

    def complete(
        self,
        run_id: str,
        tenant_id: str,
        *,
        insight_snapshot: Optional[Dict[str, Any]] = None,
        knowledge_doc_id: Optional[str] = None,
        error: Optional[str] = None,
        status: str = "completed",
    ) -> None:
        now = self._now()
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE insight_profile_runs
            SET status = ?, insight_snapshot_json = ?, knowledge_doc_id = ?,
                error = ?, finished_at = ?
            WHERE id = ? AND tenant_id = ?
            """,
            (
                status,
                json.dumps(insight_snapshot or {}, ensure_ascii=False),
                knowledge_doc_id,
                error,
                now,
                run_id,
                tenant_id,
            ),
        )
        conn.commit()

    def _row_to_run(self, row) -> Optional[InsightProfileRun]:
        if not row:
            return None
        try:
            budget = json.loads(row[5] or "{}")
        except json.JSONDecodeError:
            budget = {}
        try:
            progress = json.loads(row[6] or "{}")
        except json.JSONDecodeError:
            progress = {}
        snapshot = None
        if row[7]:
            try:
                snapshot = json.loads(row[7])
            except json.JSONDecodeError:
                snapshot = {}
        return InsightProfileRun(
            id=row[0],
            datasource_id=row[1],
            tenant_id=row[2],
            capability_version=row[3],
            status=row[4],
            budget_json=budget,
            progress_json=progress,
            insight_snapshot_json=snapshot,
            knowledge_doc_id=row[8],
            error=row[9],
            started_at=row[10],
            finished_at=row[11],
            created_at=row[12],
        )


class InsightMetricStore:
    """CRUD for insight_metrics."""

    def __init__(self, db: Database):
        self.db = db

    def _now(self) -> str:
        return get_local_now().isoformat()

    def replace_draft_metrics(
        self,
        datasource_id: str,
        tenant_id: str,
        candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Replace profile-sourced draft metrics for a datasource.

        Returns {"inserted": int, "skipped": [metric_key,...]} so callers
        can surface candidates that collide with approved rows on the
        UNIQUE(datasource_id, tenant_id, metric_key) constraint.
        """
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM insight_metrics
            WHERE datasource_id = ? AND tenant_id = ? AND source = 'profile' AND status = 'draft'
            """,
            (datasource_id, tenant_id),
        )
        now = self._now()
        inserted = 0
        skipped: List[str] = []
        for m in candidates:
            key = (m.get("key") or m.get("metric_key") or "").strip()
            if not key:
                continue
            mid = str(uuid.uuid4())
            tables = m.get("tables") or []
            cursor.execute(
                """
                INSERT OR IGNORE INTO insight_metrics (
                    id, datasource_id, tenant_id, metric_key, display_name, definition,
                    sql_template, tables_json, status, source, confidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', 'profile', ?, ?, ?)
                """,
                (
                    mid,
                    datasource_id,
                    tenant_id,
                    key,
                    m.get("display_name") or key,
                    m.get("definition") or "",
                    m.get("sql_template") or "",
                    json.dumps(tables, ensure_ascii=False),
                    float(m.get("confidence") or 0),
                    now,
                    now,
                ),
            )
            if cursor.rowcount and cursor.rowcount > 0:
                inserted += 1
            else:
                skipped.append(key)
        conn.commit()
        return {"inserted": inserted, "skipped": skipped}

    def list_by_datasource(
        self, datasource_id: str, tenant_id: str = "default"
    ) -> List[InsightMetric]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM insight_metrics
            WHERE datasource_id = ? AND tenant_id = ?
            ORDER BY updated_at DESC
            """,
            (datasource_id, tenant_id),
        )
        return [m for row in cursor.fetchall() if (m := self._row_to_metric(row))]

    def _row_to_metric(self, row) -> Optional[InsightMetric]:
        if not row:
            return None
        try:
            tables = json.loads(row[7] or "[]")
        except json.JSONDecodeError:
            tables = []
        return InsightMetric(
            id=row[0],
            datasource_id=row[1],
            tenant_id=row[2],
            metric_key=row[3],
            display_name=row[4],
            definition=row[5],
            sql_template=row[6] or "",
            tables_json=tables,
            status=row[8],
            source=row[9],
            confidence=float(row[10] or 0),
            created_at=row[11],
            updated_at=row[12],
        )
