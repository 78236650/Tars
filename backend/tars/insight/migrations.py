"""INS-2.0 schema migrations and workflow backfill."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .version import INS_VERSION


def _table_columns(cursor: sqlite3.Cursor, table: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def ensure_sessions_metadata_json(cursor: sqlite3.Cursor) -> None:
    cols = _table_columns(cursor, "sessions")
    if "metadata_json" not in cols:
        cursor.execute(
            "ALTER TABLE sessions ADD COLUMN metadata_json TEXT DEFAULT '{}'"
        )


def ensure_insight_question_log(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS insight_question_log (
            id TEXT PRIMARY KEY,
            datasource_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            question TEXT NOT NULL,
            question_embedding BLOB,
            metric_key TEXT,
            sql TEXT NOT NULL,
            branch TEXT NOT NULL,
            outcome TEXT NOT NULL,
            feedback INTEGER,
            caliber_tier TEXT NOT NULL,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_qlog_ds "
        "ON insight_question_log(datasource_id, tenant_id, created_at DESC)"
    )


def ensure_insight_metric_adoptions(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS insight_metric_adoptions (
            id TEXT PRIMARY KEY,
            metric_id TEXT NOT NULL,
            proposed_by TEXT NOT NULL,
            status TEXT NOT NULL,
            reviewer_id TEXT,
            review_note TEXT,
            created_at TEXT NOT NULL,
            reviewed_at TEXT
        )
    """)


def migrate_insight_metrics_v2(cursor: sqlite3.Cursor) -> None:
    cols = _table_columns(cursor, "insight_metrics")
    if "version" in cols:
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_insight_metrics_key_ver "
            "ON insight_metrics(datasource_id, tenant_id, metric_key, version)"
        )
        return

    cursor.execute("""
        CREATE TABLE insight_metrics_ins2 (
            id TEXT PRIMARY KEY,
            datasource_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            metric_key TEXT NOT NULL,
            display_name TEXT NOT NULL,
            definition TEXT NOT NULL,
            sql_template TEXT DEFAULT '',
            tables_json TEXT DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'draft',
            source TEXT NOT NULL DEFAULT 'profile',
            confidence REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            superseded_by TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO insight_metrics_ins2 (
            id, datasource_id, tenant_id, metric_key, display_name, definition,
            sql_template, tables_json, status, source, confidence,
            created_at, updated_at, version, superseded_by
        )
        SELECT
            id, datasource_id, tenant_id, metric_key, display_name, definition,
            sql_template, tables_json, status, source, confidence,
            created_at, updated_at, 1, NULL
        FROM insight_metrics
    """)
    cursor.execute("DROP TABLE insight_metrics")
    cursor.execute("ALTER TABLE insight_metrics_ins2 RENAME TO insight_metrics")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_insight_metrics_ds "
        "ON insight_metrics(datasource_id, tenant_id)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_insight_metrics_key_ver "
        "ON insight_metrics(datasource_id, tenant_id, metric_key, version)"
    )


def backfill_insight_workflow_states(cursor: sqlite3.Cursor) -> int:
    """Set schema_snapshot.insight.workflow.state from latest profile run."""
    cursor.execute("SELECT id, tenant_id, schema_snapshot FROM bi_datasources")
    rows = cursor.fetchall()
    updated = 0
    for ds_id, tenant_id, snapshot_raw in rows:
        try:
            snapshot = json.loads(snapshot_raw or "{}")
        except json.JSONDecodeError:
            snapshot = {}
        insight = snapshot.setdefault("insight", {})
        workflow = insight.setdefault("workflow", {})
        if workflow.get("ins_version") in ("INS-2.0.0", "INS-2.1.0") and workflow.get("state"):
            continue

        cursor.execute(
            """
            SELECT status FROM insight_profile_runs
            WHERE datasource_id = ? AND tenant_id = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (ds_id, tenant_id),
        )
        run_row = cursor.fetchone()
        if run_row and run_row[0] == "completed":
            state = "ready"
        elif run_row and run_row[0] in ("pending", "running"):
            state = "forging"
        elif run_row and run_row[0] == "failed":
            state = "forge_failed"
        else:
            state = "needs_forge"

        workflow.update(
            {
                "state": state,
                "ins_version": INS_VERSION,
            }
        )
        insight["workflow"] = workflow
        snapshot["insight"] = insight
        cursor.execute(
            "UPDATE bi_datasources SET schema_snapshot = ? WHERE id = ? AND tenant_id = ?",
            (json.dumps(snapshot, ensure_ascii=False), ds_id, tenant_id),
        )
        updated += 1
    return updated


def run_insight_ins2_migrations(cursor: sqlite3.Cursor) -> None:
    ensure_sessions_metadata_json(cursor)
    ensure_insight_question_log(cursor)
    ensure_insight_metric_adoptions(cursor)
    migrate_insight_metrics_v2(cursor)
    backfill_insight_workflow_states(cursor)
