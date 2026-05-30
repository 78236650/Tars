#!/usr/bin/env python3
"""Migrate knowledge collections/chunks to v5.0 org scope (tenant_id=org_default)."""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from tars.org import ORG_ID  # noqa: E402


def _table_has_column(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def migrate_knowledge(db_path: str, dry_run: bool = False) -> dict:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {"org_id": ORG_ID, "document_collections": 0, "knowledge_chunks": 0}

    cursor.execute(
        "SELECT COUNT(*) FROM document_collections WHERE tenant_id != ?",
        (ORG_ID,),
    )
    stats["document_collections"] = cursor.fetchone()[0]
    if not dry_run and stats["document_collections"]:
        cursor.execute(
            "UPDATE document_collections SET tenant_id = ? WHERE tenant_id != ?",
            (ORG_ID, ORG_ID),
        )

    if _table_has_column(cursor, "knowledge_chunks", "tenant_id"):
        cursor.execute(
            "SELECT COUNT(*) FROM knowledge_chunks WHERE tenant_id != ?",
            (ORG_ID,),
        )
        stats["knowledge_chunks"] = cursor.fetchone()[0]
        if not dry_run and stats["knowledge_chunks"]:
            cursor.execute(
                "UPDATE knowledge_chunks SET tenant_id = ? WHERE tenant_id != ?",
                (ORG_ID, ORG_ID),
            )

    if not dry_run:
        conn.commit()
    conn.close()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate knowledge base to v5 org scope")
    parser.add_argument(
        "--db",
        default=str(ROOT / "backend" / "data" / "tars.db"),
        help="Path to SQLite database",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    args = parser.parse_args()
    stats = migrate_knowledge(args.db, dry_run=args.dry_run)
    mode = "dry-run" if args.dry_run else "applied"
    print(
        f"[migrate_knowledge_v5_org] {mode}: "
        f"document_collections={stats['document_collections']}, "
        f"knowledge_chunks={stats['knowledge_chunks']} -> tenant_id={stats['org_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
