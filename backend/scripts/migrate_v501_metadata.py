#!/usr/bin/env python3
"""v5.0.1 migration: add metadata_json columns for DeepSeek thinking mode support.

DeepSeek's thinking mode requires `reasoning_content` to be preserved across
conversation turns and passed back to the API on every request. This column
stores that content (and any future assistant metadata) in the messages table.

Run:  python backend/scripts/migrate_v501_metadata.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from tars.database.driver import detect_dialect, parse_database_url, create_connection_factory


def _ensure_column(conn, table: str, column: str, col_type: str) -> bool:
    """Add a column if it does not already exist. Returns True if added."""
    cursor = conn.cursor()
    dialect = detect_dialect(parse_database_url())

    if dialect == "postgres":
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = %s",
            (table, column),
        )
        exists = cursor.fetchone() is not None
    else:
        cols = {r[1] for r in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
        exists = column in cols

    if exists:
        print(f"  [skip] {table}.{column} already exists")
        return False

    if dialect == "postgres":
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    else:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

    conn.commit()
    print(f"  [ok] {table}.{column} added")
    return True


def main() -> int:
    factory = create_connection_factory(parse_database_url())
    conn = factory.get_conn()

    changed = 0
    changed += _ensure_column(conn, "sessions", "metadata_json", "TEXT")
    changed += _ensure_column(conn, "messages", "metadata_json", "TEXT")

    if changed:
        print("\n[v501] metadata_json columns added — DeepSeek thinking mode ready.")
    else:
        print("\n[v501] No changes needed.")

    factory.release(conn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
