#!/usr/bin/env python3
"""Migrate memories to v5.0 org scope (tenant_id=org_default, user_id for private rows)."""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from tars.org import ORG_ID  # noqa: E402


def migrate_memories(db_path: str, dry_run: bool = False) -> dict:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE memories ADD COLUMN user_id TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute("SELECT id, tenant_id, scope FROM memories")
    rows = cursor.fetchall()
    updated = 0

    for memory_id, old_tenant_id, scope in rows:
        new_user_id = None
        if scope == "private" and old_tenant_id and old_tenant_id != ORG_ID:
            new_user_id = old_tenant_id
        if not dry_run:
            cursor.execute(
                "UPDATE memories SET tenant_id = ?, user_id = ? WHERE id = ?",
                (ORG_ID, new_user_id, memory_id),
            )
        updated += 1

    if not dry_run:
        conn.commit()
    conn.close()
    return {"rows": len(rows), "updated": updated, "org_id": ORG_ID}


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate memories to v5 org scope")
    parser.add_argument(
        "--db",
        default=str(ROOT / "backend" / "data" / "tars.db"),
        help="Path to SQLite database",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    args = parser.parse_args()
    stats = migrate_memories(args.db, dry_run=args.dry_run)
    mode = "dry-run" if args.dry_run else "applied"
    print(f"[migrate_memories_v5_org] {mode}: {stats['updated']} row(s) -> tenant_id={stats['org_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
