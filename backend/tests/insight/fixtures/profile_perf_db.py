"""Build configurable SQLite databases for InsightForge profile perf tests."""
from __future__ import annotations

import sqlite3
from pathlib import Path


def build_sqlite(
    path: Path | str,
    *,
    n_tables: int = 5,
    n_columns: int = 8,
    n_rows: int = 50,
    prefix: str = "t_",
) -> str:
    """Create a SQLite file with n_tables × n_columns × n_rows for perf fixtures."""
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    for i in range(n_tables):
        table = f"{prefix}{i}"
        col_defs = ["id INTEGER PRIMARY KEY"]
        for j in range(n_columns - 1):
            col_defs.append(f"col_{j} TEXT")
        conn.execute(f"CREATE TABLE {table} ({', '.join(col_defs)})")
        rows = [
            (r, *[f"{table}_{r}_{j}" for j in range(n_columns - 1)])
            for r in range(1, n_rows + 1)
        ]
        placeholders = ", ".join(["?"] * n_columns)
        conn.executemany(
            f"INSERT INTO {table} VALUES ({placeholders})",
            rows,
        )
    conn.commit()
    conn.close()
    return f"sqlite:///{db_path}"


def insert_extra_rows(path: Path | str, table: str, n: int = 100) -> None:
    """Insert additional rows into a table for sample drift tests."""
    conn = sqlite3.connect(str(path))
    info = conn.execute(f"PRAGMA table_info({table})").fetchall()
    col_names = [row[1] for row in info]
    non_pk = [c for c in col_names if c != "id"]
    max_id = conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table}").fetchone()[0]
    for i in range(n):
        rid = max_id + i + 1
        vals = [rid] + [f"drift_{i}_{j}" for j in range(len(non_pk))]
        placeholders = ", ".join(["?"] * len(col_names))
        conn.execute(
            f"INSERT INTO {table} ({', '.join(col_names)}) VALUES ({placeholders})",
            vals,
        )
    conn.commit()
    conn.close()


def alter_add_column(path: Path | str, table: str, col: str, dtype: str = "TEXT") -> None:
    conn = sqlite3.connect(str(path))
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {dtype}")
    conn.commit()
    conn.close()


def schema_dict_from_sqlite(path: Path | str, *, prefix: str = "t_") -> dict:
    """Minimal schema dict compatible with StatsCollector tests."""
    conn = sqlite3.connect(str(path))
    tables: dict = {}
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ):
        cols = []
        for cid, cname, ctype, notnull, _, pk in conn.execute(f"PRAGMA table_info({name})"):
            cols.append(
                {
                    "name": cname,
                    "type": ctype or "TEXT",
                    "nullable": not notnull,
                    "primary_key": pk > 0,
                }
            )
        pks = [c["name"] for c in cols if c.get("primary_key")]
        tables[name] = {"columns": cols, "primary_key": pks, "foreign_keys": []}
    conn.close()
    return {"tables": tables}
