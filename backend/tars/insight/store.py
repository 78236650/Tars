"""InsightForge persistence (profile runs + metrics)."""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from ..database.base import Database, get_local_now
from ..database.sqlite_retry import run_sqlite_with_retry
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

        def _replace() -> Dict[str, Any]:
            return self._replace_draft_metrics_tx(datasource_id, tenant_id, candidates)

        return run_sqlite_with_retry(_replace)

    def _replace_draft_metrics_tx(
        self,
        datasource_id: str,
        tenant_id: str,
        candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
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

    def get_by_id(self, metric_id: str, tenant_id: str) -> Optional[InsightMetric]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM insight_metrics WHERE id = ? AND tenant_id = ?",
            (metric_id, tenant_id),
        )
        return self._row_to_metric(cursor.fetchone())

    def get_current_by_key(
        self, datasource_id: str, tenant_id: str, metric_key: str
    ) -> Optional[InsightMetric]:
        """Latest non-superseded row for a metric key."""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM insight_metrics
            WHERE datasource_id = ? AND tenant_id = ? AND metric_key = ?
              AND superseded_by IS NULL
            ORDER BY version DESC
            LIMIT 1
            """,
            (datasource_id, tenant_id, metric_key),
        )
        return self._row_to_metric(cursor.fetchone())

    def get_by_key(
        self, datasource_id: str, tenant_id: str, metric_key: str
    ) -> Optional[InsightMetric]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM insight_metrics
            WHERE datasource_id = ? AND tenant_id = ? AND metric_key = ?
            ORDER BY version DESC
            LIMIT 1
            """,
            (datasource_id, tenant_id, metric_key),
        )
        return self._row_to_metric(cursor.fetchone())

    def list_approved(
        self, datasource_id: str, tenant_id: str = "default"
    ) -> List[InsightMetric]:
        return [
            m
            for m in self.list_by_datasource(datasource_id, tenant_id)
            if m.status == "approved"
        ]

    def list_by_keys(
        self,
        datasource_id: str,
        tenant_id: str,
        metric_keys: List[str],
    ) -> List[InsightMetric]:
        if not metric_keys:
            return []
        keys = [k for k in metric_keys if k]
        placeholders = ",".join("?" * len(keys))
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT * FROM insight_metrics
            WHERE datasource_id = ? AND tenant_id = ?
              AND metric_key IN ({placeholders})
            """,
            (datasource_id, tenant_id, *keys),
        )
        return [m for row in cursor.fetchall() if (m := self._row_to_metric(row))]

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

    def create_draft_from_log(
        self,
        *,
        datasource_id: str,
        tenant_id: str,
        metric_key: str,
        display_name: str,
        definition: str,
        sql_template: str,
        source: str = "adhoc",
    ) -> InsightMetric:
        mid = str(uuid.uuid4())
        now = self._now()
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO insight_metrics (
                id, datasource_id, tenant_id, metric_key, display_name, definition,
                sql_template, tables_json, status, source, confidence, created_at, updated_at,
                version, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, '[]', 'draft', ?, 0.5, ?, ?, 1, NULL)
            """,
            (
                mid,
                datasource_id,
                tenant_id,
                metric_key,
                display_name,
                definition,
                sql_template,
                source,
                now,
                now,
            ),
        )
        conn.commit()
        return self.get_by_id(mid, tenant_id)  # type: ignore

    def adopt_metric(
        self,
        metric_id: str,
        tenant_id: str,
        *,
        definition: Optional[str] = None,
        sql_template: Optional[str] = None,
    ) -> InsightMetric:
        """Promote draft→approved or bump version when definition changes (row lock)."""

        def _adopt() -> InsightMetric:
            return self._adopt_metric_tx(
                metric_id, tenant_id, definition=definition, sql_template=sql_template
            )

        return run_sqlite_with_retry(_adopt)

    def _adopt_metric_tx(
        self,
        metric_id: str,
        tenant_id: str,
        *,
        definition: Optional[str] = None,
        sql_template: Optional[str] = None,
    ) -> InsightMetric:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            cursor.execute(
                "SELECT * FROM insight_metrics WHERE id = ? AND tenant_id = ?",
                (metric_id, tenant_id),
            )
            row = cursor.fetchone()
            metric = self._row_to_metric(row)
            if not metric:
                conn.rollback()
                raise ValueError("metric not found")

            new_def = (definition if definition is not None else metric.definition).strip()
            new_sql = (
                sql_template if sql_template is not None else metric.sql_template
            ).strip()
            now = self._now()

            if metric.status == "draft":
                cursor.execute(
                    """
                    UPDATE insight_metrics
                    SET status = 'approved', definition = ?, sql_template = ?,
                        updated_at = ?, source = CASE WHEN source = 'profile' THEN source ELSE 'adhoc' END
                    WHERE id = ? AND tenant_id = ?
                    """,
                    (new_def, new_sql, now, metric_id, tenant_id),
                )
                conn.commit()
                return self.get_by_id(metric_id, tenant_id)  # type: ignore

            if metric.status != "approved":
                conn.rollback()
                raise ValueError(f"cannot adopt status={metric.status}")

            if new_def == metric.definition.strip() and new_sql == (metric.sql_template or "").strip():
                cursor.execute(
                    "UPDATE insight_metrics SET updated_at = ? WHERE id = ? AND tenant_id = ?",
                    (now, metric_id, tenant_id),
                )
                conn.commit()
                return self.get_by_id(metric_id, tenant_id)  # type: ignore

            cursor.execute(
                """
                SELECT id FROM insight_metrics
                WHERE datasource_id = ? AND tenant_id = ? AND metric_key = ?
                  AND status = 'approved' AND superseded_by IS NULL AND id != ?
                """,
                (metric.datasource_id, tenant_id, metric.metric_key, metric_id),
            )
            if cursor.fetchone():
                conn.rollback()
                raise AdoptionConflictError("concurrent adoption in progress")

            new_id = str(uuid.uuid4())
            new_version = metric.version + 1
            cursor.execute(
                """
                INSERT INTO insight_metrics (
                    id, datasource_id, tenant_id, metric_key, display_name, definition,
                    sql_template, tables_json, status, source, confidence, created_at, updated_at,
                    version, superseded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?, ?, ?, ?, ?, NULL)
                """,
                (
                    new_id,
                    metric.datasource_id,
                    tenant_id,
                    metric.metric_key,
                    metric.display_name,
                    new_def,
                    new_sql,
                    json.dumps(metric.tables_json, ensure_ascii=False),
                    metric.source,
                    metric.confidence,
                    now,
                    now,
                    new_version,
                ),
            )
            cursor.execute(
                """
                UPDATE insight_metrics
                SET superseded_by = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (new_id, now, metric_id, tenant_id),
            )
            conn.commit()
            return self.get_by_id(new_id, tenant_id)  # type: ignore
        except AdoptionConflictError:
            raise
        except Exception:
            conn.rollback()
            raise

    def deprecate_metric(self, metric_id: str, tenant_id: str) -> bool:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        now = self._now()
        cursor.execute(
            """
            UPDATE insight_metrics
            SET status = 'deprecated', updated_at = ?
            WHERE id = ? AND tenant_id = ? AND status = 'approved' AND superseded_by IS NULL
            """,
            (now, metric_id, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0

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
            version=int(row[13]) if len(row) > 13 and row[13] is not None else 1,
            superseded_by=row[14] if len(row) > 14 else None,
        )


class AdoptionConflictError(Exception):
    """Concurrent adoption on the same metric key."""
