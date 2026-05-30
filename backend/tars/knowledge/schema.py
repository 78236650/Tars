"""Knowledge-base SQLite schema (v4.3.1+) and org-scoped collections."""
from __future__ import annotations

import sqlite3

from tars.org import ORG_ID


def _table_columns(cursor, table: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def ensure_knowledge_schema(db) -> None:
    """Create or migrate document_collections / document_files for knowledge KB."""
    ensure_knowledge_schema_on_conn(db._get_conn())


def ensure_knowledge_schema_on_conn(conn) -> None:
    cursor = conn.cursor()

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

    if _table_exists(cursor, "document_files"):
        cols = _table_columns(cursor, "document_files")
        # Legacy v1 table (user_id-centric) is incompatible with knowledge KB rows.
        if "collection_id" not in cols:
            cursor.execute(
                "ALTER TABLE document_files RENAME TO document_files_legacy_v1"
            )
            cols = set()

    cols = _table_columns(cursor, "document_files") if _table_exists(cursor, "document_files") else set()

    if not cols:
        cursor.execute(
            """
            CREATE TABLE document_files (
                id TEXT PRIMARY KEY,
                collection_id TEXT,
                file_name TEXT,
                file_path TEXT,
                file_type TEXT,
                chunk_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                doc_type TEXT DEFAULT 'generic',
                profile_ready INTEGER DEFAULT 0,
                one_liner TEXT,
                status_message TEXT,
                metadata_json TEXT,
                created_at TEXT
            )
            """
        )
    else:
        migrations = {
            "collection_id": "ALTER TABLE document_files ADD COLUMN collection_id TEXT",
            "doc_type": "ALTER TABLE document_files ADD COLUMN doc_type TEXT DEFAULT 'generic'",
            "profile_ready": "ALTER TABLE document_files ADD COLUMN profile_ready INTEGER DEFAULT 0",
            "one_liner": "ALTER TABLE document_files ADD COLUMN one_liner TEXT",
            "status_message": "ALTER TABLE document_files ADD COLUMN status_message TEXT",
            "metadata_json": "ALTER TABLE document_files ADD COLUMN metadata_json TEXT",
            "chunk_count": "ALTER TABLE document_files ADD COLUMN chunk_count INTEGER DEFAULT 0",
        }
        for col, ddl in migrations.items():
            if col not in cols:
                try:
                    cursor.execute(ddl)
                except sqlite3.OperationalError:
                    pass

    if "default_doc_type" not in _table_columns(cursor, "document_collections"):
        try:
            cursor.execute("ALTER TABLE document_collections ADD COLUMN default_doc_type TEXT")
        except sqlite3.OperationalError:
            pass

    _ensure_document_profiles_table(cursor)

    conn.commit()


def _ensure_document_profiles_table(cursor) -> None:
    if _table_exists(cursor, "document_profiles"):
        cols = _table_columns(cursor, "document_profiles")
        if "tenant_id" not in cols:
            cursor.execute(
                "ALTER TABLE document_profiles RENAME TO document_profiles_legacy_v1"
            )

    if not _table_exists(cursor, "document_profiles"):
        cursor.execute(
            """
            CREATE TABLE document_profiles (
                doc_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                collection_id TEXT NOT NULL,
                doc_type TEXT NOT NULL DEFAULT 'generic',
                title TEXT NOT NULL DEFAULT '',
                one_liner TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                key_points_json TEXT NOT NULL DEFAULT '[]',
                sections_json TEXT NOT NULL DEFAULT '[]',
                key_facts_json TEXT NOT NULL DEFAULT '[]',
                glossary_json TEXT NOT NULL DEFAULT '[]',
                qa_pairs_json TEXT NOT NULL DEFAULT '[]',
                tags_json TEXT NOT NULL DEFAULT '[]',
                confidence REAL NOT NULL DEFAULT 0.0,
                enrichment_model TEXT,
                enriched_at TEXT,
                parse_warnings_json TEXT NOT NULL DEFAULT '[]'
            )
            """
        )


def _table_exists(cursor, table: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def org_tenant_id() -> str:
    """Return org scope id stored in document_collections.tenant_id."""
    return ORG_ID
