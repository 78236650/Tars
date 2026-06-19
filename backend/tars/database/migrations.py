"""Schema version tracking and ordered migrations (TARS v5.0.5 / P4).

The legacy ``init_schema`` is idempotent (CREATE TABLE IF NOT EXISTS + guarded
ALTERs) and remains the source of the base schema. This module adds a recorded
**version** so future schema changes apply in order, exactly once, and are
auditable — the foundation later batches (A2 approval persistence, A6 decision
table) build their migrations on.

``apply_migrations(conn, dialect)`` is called at the end of schema init. Each
migration is an ``(version, description, fn)`` tuple; ``fn(cursor)`` performs
the change. Applied versions are recorded in ``schema_versions``.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Tuple

logger = logging.getLogger("tars.migrations")

Migration = Tuple[int, str, Callable]


def _m1_encrypt_api_keys(cursor) -> None:
    """v5.0.5/P6: encrypt plaintext api_key at rest + backfill api_key_hash.

    Idempotent: rows already encrypted (value starts with the enc:: prefix) are
    skipped. Login keeps working throughout because the lookup falls back to
    plaintext for any not-yet-migrated row.
    """
    from ..security.crypto import encrypt, lookup_hash, is_encrypted

    # The users table is created later by UserStore._init_tables(); on a brand
    # new DB it doesn't exist yet at schema-init time. That's fine — fresh rows
    # are encrypted at creation, so this backfill only matters for existing
    # deployments where the table is already present.
    try:
        cursor.execute("SELECT id, api_key FROM users WHERE api_key IS NOT NULL")
        rows = cursor.fetchall()
    except Exception:
        return
    for user_id, api_key in rows:
        if not api_key or is_encrypted(api_key):
            continue
        try:
            cursor.execute(
                "UPDATE users SET api_key = ?, api_key_hash = ? WHERE id = ?",
                (encrypt(api_key), lookup_hash(api_key), user_id),
            )
        except Exception:
            # api_key_hash column may not exist on a very old schema; skip.
            cursor.execute(
                "UPDATE users SET api_key = ? WHERE id = ?",
                (encrypt(api_key), user_id),
            )


def _m2_agent_decisions(cursor) -> None:
    """v5.0.5/A6: agent_decisions 表 —— 记录技能路由/记忆检索/升格等决策,
    带 trace_id 以便按请求链回溯。建表幂等;索引按 trace_id 与 session 检索。

    用 TEXT/TIMESTAMP 等方言无关类型,sqlite 与 postgres 均可。
    """
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_decisions (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL DEFAULT '',
            tenant_id TEXT NOT NULL DEFAULT 'default',
            user_id TEXT NOT NULL DEFAULT 'default',
            trace_id TEXT,
            decision_type TEXT NOT NULL,
            decision_input TEXT,
            decision_output TEXT,
            reasoning TEXT,
            created_at TIMESTAMP NOT NULL
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_decisions_trace ON agent_decisions(trace_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_decisions_session ON agent_decisions(session_id, created_at)"
    )


def _m3_dead_letter_retry(cursor) -> None:
    """v5.0.5/A7: dead_letters 增加重试追踪列(status/retry_count/last_retry_at)。

    幂等:列已存在则跳过。老库可能尚无 dead_letters 表(由 init_schema 建),
    故先确保表存在。
    """
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dead_letters (
            id TEXT PRIMARY KEY,
            op TEXT NOT NULL,
            error TEXT NOT NULL,
            session_id TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    for col, ddl in (
        ("status", "ALTER TABLE dead_letters ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'"),
        ("retry_count", "ALTER TABLE dead_letters ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0"),
        ("last_retry_at", "ALTER TABLE dead_letters ADD COLUMN last_retry_at TEXT"),
        ("payload", "ALTER TABLE dead_letters ADD COLUMN payload TEXT"),
    ):
        try:
            cursor.execute(ddl)
        except Exception:
            # 列已存在(重复迁移或老库已手工加过)——幂等跳过
            pass


def _m4_document_collections(cursor) -> None:
    """v5.0.5/A8: 补回 document_collections 表。

    commit 528d4ac(移除 knowledge 模块)误删了 SQLite 端 connection.py 的此表,
    但 connection_pg.py(Postgres)仍保留,且 insight/knowledge_publisher.py 与
    search/gateway.py 仍在使用 —— 导致 SQLite 部署跑 insight 发布/搜索时
    'no such table: document_collections' 崩溃。此迁移幂等补回,列与 PG 端对齐。
    """
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS document_collections (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            default_doc_type TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


# Ordered list of migrations. Append new ones with the next integer version.
def _m5_governance_tables(cursor) -> None:
    """治理三表: quality_rules / check_runs / rule_results。

    规则按 datasource_id(str UUID)+table_name 归属，带 user_id 对齐单组织多用户。
    """
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS quality_rules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            datasource_id TEXT NOT NULL,
            table_name TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL,
            params TEXT NOT NULL DEFAULT '{}',
            engine TEXT NOT NULL DEFAULT 'builtin',
            enabled INTEGER NOT NULL DEFAULT 1,
            user_id TEXT NOT NULL DEFAULT 'default',
            created_at TIMESTAMP
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_qrules_ds ON quality_rules(datasource_id, table_name)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS check_runs (
            id TEXT PRIMARY KEY,
            datasource_id TEXT NOT NULL,
            table_name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            total_rows INTEGER NOT NULL DEFAULT 0,
            truncated INTEGER NOT NULL DEFAULT 0,
            summary TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            user_id TEXT NOT NULL DEFAULT 'default',
            created_at TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rule_results (
            id TEXT PRIMARY KEY,
            check_run_id TEXT NOT NULL,
            rule_id TEXT NOT NULL,
            rule_name TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL DEFAULT '',
            engine TEXT NOT NULL DEFAULT 'builtin',
            passed_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            sample_violations TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_rresults_run ON rule_results(check_run_id)"
    )


def _m6_report_tables(cursor) -> None:
    """报表三表: charts / dashboards / dashboard_items。"""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS charts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            datasource_id TEXT NOT NULL,
            chart_type TEXT NOT NULL DEFAULT 'table',
            spec TEXT NOT NULL DEFAULT '{}',
            user_id TEXT NOT NULL DEFAULT 'default',
            created_at TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboards (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            params TEXT NOT NULL DEFAULT '{}',
            user_id TEXT NOT NULL DEFAULT 'default',
            created_at TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboard_items (
            id TEXT PRIMARY KEY,
            dashboard_id TEXT NOT NULL,
            chart_id TEXT NOT NULL,
            layout TEXT NOT NULL DEFAULT '{}',
            \"order\" INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def _m7_semantic_tables(cursor) -> None:
    """语义层: glossary_terms / field_semantics。"""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS glossary_terms (
            id TEXT PRIMARY KEY,
            term TEXT NOT NULL,
            definition TEXT NOT NULL DEFAULT '',
            domain TEXT NOT NULL DEFAULT 'port',
            aliases_json TEXT NOT NULL DEFAULT '[]',
            user_id TEXT NOT NULL DEFAULT 'default',
            created_at TIMESTAMP
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_glossary_domain ON glossary_terms(domain, user_id)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS field_semantics (
            id TEXT PRIMARY KEY,
            datasource_id TEXT NOT NULL,
            table_name TEXT NOT NULL DEFAULT '',
            column_name TEXT NOT NULL DEFAULT '',
            term_id TEXT,
            suggested_term TEXT,
            confidence REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'suggested',
            user_id TEXT NOT NULL DEFAULT 'default',
            created_at TIMESTAMP
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_field_sem_ds ON field_semantics(datasource_id, table_name)"
    )


def _m8_insight_ins2_tables(cursor) -> None:
    """Insight INS-2 migrations (moved from connection.init_schema)."""
    from tars.insight.migrations import run_insight_ins2_migrations
    run_insight_ins2_migrations(cursor)


MIGRATIONS: List[Migration] = [
    (1, "encrypt api_key at rest + backfill api_key_hash", _m1_encrypt_api_keys),
    (2, "add agent_decisions table for decision tracing", _m2_agent_decisions),
    (3, "add dead_letters retry tracking columns", _m3_dead_letter_retry),
    (4, "restore document_collections table (sqlite)", _m4_document_collections),
    (5, "governance quality tables", _m5_governance_tables),
    (6, "report tables (charts/dashboards/dashboard_items)", _m6_report_tables),
    (7, "semantic glossary and field_semantics tables", _m7_semantic_tables),
    (8, "insight INS-2 workflow tables", _m8_insight_ins2_tables),
]


def _ensure_version_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_versions (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TIMESTAMP NOT NULL
        )
        """
    )


def _applied_versions(cursor) -> set:
    cursor.execute("SELECT version FROM schema_versions")
    return {row[0] for row in cursor.fetchall()}


def apply_migrations(conn, dialect: str = "sqlite") -> int:
    """Apply any unapplied migrations in version order. Idempotent.

    Returns the number of migrations applied this call. Each migration runs in
    the caller's connection; a failure raises so startup fails loudly rather
    than leaving a half-migrated schema.
    """
    cursor = conn.cursor()
    _ensure_version_table(cursor)
    conn.commit()

    applied = _applied_versions(cursor)
    pending = sorted((m for m in MIGRATIONS if m[0] not in applied), key=lambda m: m[0])
    if not pending:
        return 0

    from datetime import datetime, timezone, timedelta

    count = 0
    for version, description, fn in pending:
        logger.info("applying migration %s: %s", version, description)
        try:
            fn(cursor)
            now = datetime.now(timezone(timedelta(hours=8))).isoformat()
            placeholder = "%s" if dialect == "postgres" else "?"
            cursor.execute(
                f"INSERT INTO schema_versions (version, description, applied_at) "
                f"VALUES ({placeholder}, {placeholder}, {placeholder})",
                (version, description, now),
            )
            conn.commit()
            count += 1
        except Exception:
            conn.rollback()
            logger.exception("migration %s failed; rolled back", version)
            raise
    return count


def current_version(conn) -> int:
    """Highest applied schema version, or 0 if none."""
    cursor = conn.cursor()
    _ensure_version_table(cursor)
    cursor.execute("SELECT COALESCE(MAX(version), 0) FROM schema_versions")
    return cursor.fetchone()[0]

