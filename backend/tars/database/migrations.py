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


# Ordered list of migrations. Append new ones with the next integer version.
MIGRATIONS: List[Migration] = [
    (1, "encrypt api_key at rest + backfill api_key_hash", _m1_encrypt_api_keys),
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

