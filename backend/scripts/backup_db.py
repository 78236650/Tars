#!/usr/bin/env python
"""Database backup utility (TARS v5.0.5 / P4).

SQLite: uses the online ``.backup`` API for a consistent snapshot even while
the app is running. Postgres: shells out to ``pg_dump``. Backups are written to
``data/backups/`` (override with ``TARS_BACKUP_DIR``) with a timestamped name,
and old backups beyond ``--keep`` are pruned.

Usage:
    python scripts/backup_db.py            # one snapshot, keep newest 7
    python scripts/backup_db.py --keep 30
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tars.database.driver import parse_database_url, detect_dialect  # noqa: E402


def _backup_dir() -> Path:
    d = os.getenv("TARS_BACKUP_DIR")
    if d:
        path = Path(d)
    else:
        path = Path(__file__).resolve().parents[1] / "data" / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _timestamp() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d-%H%M%S")


def _backup_sqlite(src_path: str, dest: Path) -> None:
    """Consistent online snapshot via the SQLite backup API."""
    src = sqlite3.connect(src_path)
    try:
        out = sqlite3.connect(str(dest))
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()


def _backup_postgres(url: str, dest: Path) -> None:
    subprocess.run(["pg_dump", "--no-owner", "--file", str(dest), url], check=True)


def _prune(backup_dir: Path, prefix: str, keep: int) -> list[str]:
    files = sorted(
        backup_dir.glob(f"{prefix}-*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    removed = []
    for old in files[keep:]:
        removed.append(old.name)
        old.unlink()
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up the TARS database")
    parser.add_argument("--keep", type=int, default=7, help="number of backups to retain")
    args = parser.parse_args()

    url = parse_database_url()
    dialect = detect_dialect(url)
    backup_dir = _backup_dir()
    ts = _timestamp()

    if dialect == "postgres":
        dest = backup_dir / f"tars-pg-{ts}.sql"
        _backup_postgres(url, dest)
        prefix = "tars-pg"
    else:
        dest = backup_dir / f"tars-sqlite-{ts}.db"
        _backup_sqlite(url, dest)
        prefix = "tars-sqlite"

    size = dest.stat().st_size
    print(f"Backup written: {dest} ({size} bytes)")

    removed = _prune(backup_dir, prefix, args.keep)
    if removed:
        print(f"Pruned {len(removed)} old backup(s): {', '.join(removed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

