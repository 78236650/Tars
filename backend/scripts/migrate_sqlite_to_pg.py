#!/usr/bin/env python3
"""Migrate TARS data from SQLite (backend/data/tars.db) to PostgreSQL.

Usage:
  export DATABASE_URL=postgresql://tars:tars@localhost:5432/tars
  python3 scripts/migrate_sqlite_to_pg.py --dry-run
  python3 scripts/migrate_sqlite_to_pg.py --source /path/to/tars.db

Steps:
  1. Read all rows from the SQLite source (users live in the same tars.db via UserStore).
  2. Ensure target PG schema via ConnectionManager (init_schema_postgres).
  3. Copy tables in FK-safe order (sessions before messages, etc.).
  4. Apply v5 org migrations: tenant_id -> org_default, memories user_id backfill.

Notes:
  - user_store tables (users, user_sessions, subagent_*) are in tars.db, not a separate file.
  - memories_fts (SQLite virtual table) is skipped; PG uses ILIKE / to_tsvector at runtime.
  - knowledge_chunks is created on target if missing (sqlite_store fallback table).
  - Use --dry-run to print per-table row counts without writing.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from tars.database.base import Database  # noqa: E402
from tars.database.driver import detect_dialect, parse_database_url  # noqa: E402
from tars.org import ORG_ID  # noqa: E402

# FK-safe copy order; sqlite-only virtual tables omitted.
TABLE_COPY_ORDER: list[str] = [
    "users",
    "user_sessions",
    "subagent_config",
    "subagent_tasks",
    "core_memory",
    "global_state",
    "custom_models",
    "endpoints",
    "entities",
    "entity_aliases",
    "document_collections",
    "kb_documents",
    "document_files",
    "document_profiles",
    "knowledge_chunks",
    "kb_chunks",
    "cronjobs",
    "sessions",
    "messages",
    "memories",
    "core_memory_blocks",
    "auth_tokens",
    "sessions_metadata",
    "working_contexts",
    "dead_letters",
    "audit_logs",
    "approval_requests",
    "transcriptions",
    "datasources",
    "reminder_notifications",
    "memory_entity_links",
    "memory_relations",
    "memory_tree_nodes",
    "memory_tree_bindings",
    "agent_tasks",
    "agent_task_outputs",
    "agent_collaboration_ctx",
    "interaction_stats",
    "provider_usage",
    "evolution_events",
    "evolution_apply_log",
    "vp_berths",
    "vp_vessels",
    "vp_voyages",
    "vp_assignments",
    "vp_plan_runs",
]

KNOWLEDGE_CHUNKS_DDL = """
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_total INTEGER NOT NULL,
    file_name TEXT DEFAULT '',
    content TEXT NOT NULL,
    embedding BYTEA,
    created_at TEXT NOT NULL,
    metadata_json TEXT DEFAULT '{}'
)
"""


def _sqlite_tables(conn: sqlite3.Connection) -> set[str]:
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return {row[0] for row in cur.fetchall()}


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def _pg_columns(db: Database, table: str) -> list[str]:
    cur = db._get_conn().cursor()
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = ?
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return [row[0] for row in cur.fetchall()]


def _fetch_rows(conn: sqlite3.Connection, table: str, columns: Sequence[str]) -> list[tuple]:
    col_list = ", ".join(columns)
    cur = conn.cursor()
    cur.execute(f"SELECT {col_list} FROM {table}")
    return cur.fetchall()


def _insert_rows(
    db: Database,
    table: str,
    columns: Sequence[str],
    rows: Iterable[tuple],
    dry_run: bool,
) -> int:
    rows = list(rows)
    if not rows:
        return 0
    if dry_run:
        return len(rows)

    col_list = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    cur = db._get_conn().cursor()
    for row in rows:
        cur.execute(sql, row)
    db._get_conn().commit()
    return len(rows)


def apply_v5_org_migrations(db: Database, dry_run: bool) -> dict[str, int]:
    """tenant_id -> org_default; private memories user_id backfill from legacy tenant_id."""
    stats = {"memories_tenant": 0, "memories_user_id": 0, "document_collections": 0, "knowledge_chunks": 0}
    conn = db._get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, tenant_id, scope FROM memories")
    memory_rows = cur.fetchall()
    for memory_id, old_tenant_id, scope in memory_rows:
        new_user_id = None
        if scope == "private" and old_tenant_id and old_tenant_id != ORG_ID:
            new_user_id = old_tenant_id
            stats["memories_user_id"] += 1
        if old_tenant_id != ORG_ID:
            stats["memories_tenant"] += 1
        if not dry_run:
            cur.execute(
                "UPDATE memories SET tenant_id = ?, user_id = ? WHERE id = ?",
                (ORG_ID, new_user_id, memory_id),
            )

    for table in ("document_collections", "knowledge_chunks"):
        cur.execute(
            f"SELECT COUNT(*) FROM information_schema.columns "
            f"WHERE table_schema='public' AND table_name=? AND column_name='tenant_id'",
            (table,),
        )
        if not cur.fetchone()[0]:
            continue
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE tenant_id != ?", (ORG_ID,))
        count = int(cur.fetchone()[0] or 0)
        stats[table] = count
        if count and not dry_run:
            cur.execute(
                f"UPDATE {table} SET tenant_id = ? WHERE tenant_id != ?",
                (ORG_ID, ORG_ID),
            )

    if not dry_run:
        conn.commit()
    return stats


def migrate(source_path: str, target_url: str | None, dry_run: bool) -> dict[str, Any]:
    target_url = target_url or parse_database_url()
    if detect_dialect(target_url) != "postgres":
        raise SystemExit(f"DATABASE_URL must be PostgreSQL, got: {target_url}")

    src = sqlite3.connect(source_path)
    src.row_factory = sqlite3.Row
    source_tables = _sqlite_tables(src)

    db = Database(target_url)
    try:
        tgt_conn = db._get_conn()
        tgt_cur = tgt_conn.cursor()
        tgt_cur.execute(KNOWLEDGE_CHUNKS_DDL)
        tgt_conn.commit()

        table_stats: dict[str, int] = {}
        ordered = [t for t in TABLE_COPY_ORDER if t in source_tables]
        extras = sorted(source_tables - set(TABLE_COPY_ORDER) - {"memories_fts"})
        for table in ordered + extras:
            if table.startswith("document_files_legacy") or table.startswith("document_profiles_legacy"):
                continue
            src_cols = _sqlite_columns(src, table)
            if not src_cols:
                continue
            try:
                tgt_cols = _pg_columns(db, table)
            except Exception:
                tgt_cols = []
            if not tgt_cols:
                print(f"[skip] {table}: not in target schema")
                continue
            common = [c for c in src_cols if c in tgt_cols]
            if not common:
                print(f"[skip] {table}: no overlapping columns")
                continue
            rows = _fetch_rows(src, table, common)
            copied = _insert_rows(db, table, common, rows, dry_run)
            table_stats[table] = copied
            print(f"[{'dry-run' if dry_run else 'copy'}] {table}: {copied} row(s)")

        org_stats = apply_v5_org_migrations(db, dry_run)
        return {"tables": table_stats, "v5_org": org_stats, "org_id": ORG_ID}
    finally:
        db.close()
        src.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate TARS SQLite database to PostgreSQL")
    parser.add_argument(
        "--source",
        default=str(ROOT / "backend" / "data" / "tars.db"),
        help="Path to SQLite source database (default: backend/data/tars.db)",
    )
    parser.add_argument(
        "--target",
        default=os.environ.get("DATABASE_URL") or os.environ.get("TARS_DATABASE_URL"),
        help="PostgreSQL DATABASE_URL (default: env DATABASE_URL)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report row counts without writing")
    args = parser.parse_args()

    if not Path(args.source).is_file():
        raise SystemExit(f"Source database not found: {args.source}")
    if not args.target:
        raise SystemExit("Set DATABASE_URL or pass --target postgresql://...")

    stats = migrate(args.source, args.target, dry_run=args.dry_run)
    mode = "dry-run" if args.dry_run else "applied"
    total = sum(stats["tables"].values())
    print(
        f"[migrate_sqlite_to_pg] {mode}: copied {total} row(s) across "
        f"{len(stats['tables'])} table(s); v5 org={stats['org_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
