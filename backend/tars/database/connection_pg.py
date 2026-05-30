"""Postgres schema initialization — mirrors connection.init_schema without SQLite-only objects."""

from __future__ import annotations

import json
from typing import Any

from tars.database.models import get_local_now
from tars.database.sql_dialect import insert_upsert
from tars.knowledge.schema import org_tenant_id


def _exec(cursor, sql: str, params: tuple[Any, ...] | None = None) -> None:
    if params is None:
        cursor.execute(sql)
    else:
        cursor.execute(sql, params)


def init_schema_postgres(conn) -> None:
    """Create TARS core tables on Postgres (no FTS5 virtual tables)."""
    cursor = conn.cursor()

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            agent_id TEXT,
            user_id TEXT,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            title TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            summary TEXT
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            content TEXT NOT NULL,
            category TEXT NOT NULL,
            importance REAL DEFAULT 0.5,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            last_accessed TIMESTAMP,
            embedding BYTEA,
            scope TEXT NOT NULL DEFAULT 'private',
            user_id TEXT,
            access_count INTEGER DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'conversation',
            event_time TIMESTAMP,
            entity_refs TEXT,
            pinned INTEGER DEFAULT 0,
            compressed_from TEXT,
            memory_type TEXT NOT NULL DEFAULT 'episodic',
            promotion_group_id TEXT,
            kb_doc_id TEXT,
            kb_promotion_status TEXT
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS core_memory (
            id SERIAL PRIMARY KEY,
            key TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS core_memory_blocks (
            name TEXT NOT NULL,
            tenant_id TEXT NOT NULL DEFAULT 'org_default',
            user_id TEXT NOT NULL DEFAULT 'default',
            content TEXT NOT NULL DEFAULT '',
            updated_at TEXT,
            UNIQUE(tenant_id, user_id, name)
        )
        """,
    )

    _default_blocks = {
        "persona": (
            "TARS：理性、简洁、注重证据的工程助手。回答以代码/事实为主，避免空话。"
        ),
        "user_profile": "（暂未学习到用户信息）",
        "project_context": "（暂未记录项目上下文）",
        "working_principles": "（暂未累积协作准则）",
    }
    _blocks_now = get_local_now().isoformat()
    upsert_blocks = insert_upsert(
        "postgres",
        "core_memory_blocks",
        ["name", "tenant_id", "user_id", "content", "updated_at"],
        conflict_cols=["tenant_id", "user_id", "name"],
    )
    for _block_name, _block_content in _default_blocks.items():
        _exec(
            cursor,
            upsert_blocks,
            (_block_name, "org_default", "default", _block_content, _blocks_now),
        )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS global_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS cronjobs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            cron_expression TEXT NOT NULL,
            task_type TEXT NOT NULL,
            task_config TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            last_run TIMESTAMP,
            next_run TIMESTAMP
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS sessions_metadata (
            session_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (session_id, key)
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS working_contexts (
            tenant_id TEXT NOT NULL DEFAULT 'default',
            session_id TEXT NOT NULL,
            focus_entities TEXT NOT NULL DEFAULT '[]',
            current_intent TEXT NOT NULL DEFAULT 'unknown',
            intent_confidence REAL NOT NULL DEFAULT 0,
            open_threads TEXT NOT NULL DEFAULT '[]',
            active_skills TEXT NOT NULL DEFAULT '[]',
            last_scene_snapshot TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, session_id)
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS dead_letters (
            id TEXT PRIMARY KEY,
            op TEXT NOT NULL,
            error TEXT NOT NULL,
            session_id TEXT,
            created_at TEXT NOT NULL
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            user_id TEXT NOT NULL DEFAULT 'default',
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            detail TEXT NOT NULL,
            client_ip TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS approval_requests (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            user_id TEXT NOT NULL DEFAULT 'default',
            session_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            arguments TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL,
            resolved_at TIMESTAMP,
            resolved_by TEXT NOT NULL DEFAULT ''
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS transcriptions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT,
            file_size INTEGER,
            duration REAL,
            language TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            transcript TEXT,
            segments TEXT,
            summary TEXT,
            summary_type TEXT,
            key_points TEXT,
            model_used TEXT,
            created_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT,
            approved_at TEXT,
            knowledge_doc_id TEXT
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS document_files (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT,
            file_size INTEGER,
            file_type TEXT,
            file_hash TEXT,
            status TEXT NOT NULL DEFAULT 'uploaded',
            created_at TIMESTAMP NOT NULL,
            chunk_count INTEGER DEFAULT 0,
            kb_doc_id TEXT,
            collection_id TEXT,
            doc_type TEXT DEFAULT 'generic',
            profile_ready INTEGER DEFAULT 0,
            one_liner TEXT,
            status_message TEXT,
            metadata_json TEXT
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS kb_chunks (
            id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            tokens INTEGER DEFAULT 0,
            created_at TIMESTAMP NOT NULL,
            FOREIGN KEY (doc_id) REFERENCES document_files(id)
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS kb_documents (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            user_id TEXT NOT NULL DEFAULT 'default',
            title TEXT NOT NULL,
            source_file TEXT,
            source_type TEXT NOT NULL DEFAULT 'upload',
            content_hash TEXT,
            chunk_count INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS document_profiles (
            doc_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            collection_id TEXT NOT NULL DEFAULT '',
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
            parse_warnings_json TEXT NOT NULL DEFAULT '[]',
            keywords TEXT NOT NULL DEFAULT '[]',
            topics TEXT NOT NULL DEFAULT '[]',
            language TEXT NOT NULL DEFAULT 'unknown',
            created_at TEXT,
            updated_at TEXT
        )
        """,
    )

    _exec(
        cursor,
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
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS datasources (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            name TEXT NOT NULL,
            db_type TEXT NOT NULL,
            host TEXT NOT NULL,
            port INTEGER NOT NULL,
            database_name TEXT NOT NULL,
            username TEXT NOT NULL,
            password_encrypted TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS reminder_notifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            session_id TEXT,
            task_name TEXT NOT NULL,
            message TEXT NOT NULL,
            delivery_status TEXT NOT NULL,
            error_message TEXT,
            summary_logs TEXT NOT NULL DEFAULT '[]',
            is_read INTEGER DEFAULT 0,
            triggered_at TIMESTAMP NOT NULL,
            read_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            FOREIGN KEY (job_id) REFERENCES cronjobs(id)
        )
        """,
    )
    _exec(
        cursor,
        "CREATE INDEX IF NOT EXISTS idx_reminder_notifications_user_triggered "
        "ON reminder_notifications(user_id, triggered_at DESC)",
    )
    _exec(
        cursor,
        "CREATE INDEX IF NOT EXISTS idx_reminder_notifications_job_triggered "
        "ON reminder_notifications(job_id, triggered_at DESC)",
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS custom_models (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            model TEXT NOT NULL,
            api_key TEXT,
            description TEXT,
            is_enabled INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS endpoints (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            api_key TEXT,
            models TEXT NOT NULL DEFAULT '[]',
            enabled INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
    )

    try:
        cursor.execute("SELECT COUNT(*) FROM endpoints")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "SELECT id, name, base_url, api_key, model, is_enabled, created_at, updated_at FROM custom_models"
            )
            for row in cursor.fetchall():
                mid, name, base_url, api_key, model, is_en, cat, uat = row
                models_json = json.dumps([model], ensure_ascii=False)
                _exec(
                    cursor,
                    insert_upsert(
                        "postgres",
                        "endpoints",
                        ["id", "name", "base_url", "api_key", "models", "enabled", "created_at", "updated_at"],
                        conflict_cols=["id"],
                    ),
                    (mid, name, base_url, api_key, models_json, is_en or 1, cat, uat),
                )
    except Exception:
        pass

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            aliases TEXT DEFAULT '[]',
            attributes TEXT DEFAULT '{}',
            attributes_history TEXT DEFAULT '[]',
            confidence REAL DEFAULT 0.5,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS memory_entity_links (
            memory_id TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            relation TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (memory_id, entity_id, relation)
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS memory_relations (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            weight REAL DEFAULT 1.0,
            created_at TEXT NOT NULL
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS entity_aliases (
            entity_id TEXT NOT NULL,
            alias TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'extraction',
            created_at TEXT NOT NULL,
            PRIMARY KEY (entity_id, alias)
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS memory_tree_nodes (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            label TEXT NOT NULL,
            node_type TEXT NOT NULL DEFAULT 'category',
            parent_id TEXT,
            metadata_json TEXT DEFAULT '{}',
            sort_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS memory_tree_bindings (
            node_id TEXT NOT NULL,
            memory_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (node_id, memory_id)
        )
        """,
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS agent_tasks (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            session_id TEXT NOT NULL,
            goal TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            orchestrator TEXT NOT NULL DEFAULT 'master',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
    )
    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS agent_task_outputs (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            agent_type TEXT NOT NULL,
            subtask TEXT NOT NULL,
            output TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'done',
            created_at TEXT NOT NULL
        )
        """,
    )
    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS agent_collaboration_ctx (
            task_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (task_id, key)
        )
        """,
    )
    _exec(cursor, "CREATE INDEX IF NOT EXISTS idx_task_outputs_task ON agent_task_outputs(task_id)")

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS vp_berths (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            name TEXT NOT NULL,
            length_m REAL NOT NULL,
            depth_m REAL NOT NULL,
            crane_count INTEGER NOT NULL DEFAULT 2,
            yard_zone TEXT NOT NULL DEFAULT 'A',
            position_x REAL NOT NULL DEFAULT 0,
            position_y REAL NOT NULL DEFAULT 0
        )
        """,
    )
    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS vp_vessels (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            name TEXT NOT NULL,
            imo TEXT,
            length_m REAL NOT NULL,
            draft_m REAL NOT NULL,
            priority INTEGER NOT NULL DEFAULT 0
        )
        """,
    )
    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS vp_voyages (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            vessel_id TEXT NOT NULL,
            eta TEXT NOT NULL,
            etd_est TEXT,
            cargo_teu INTEGER NOT NULL DEFAULT 0,
            target_yard_zone TEXT NOT NULL DEFAULT 'A',
            service_hours REAL NOT NULL DEFAULT 8,
            status TEXT NOT NULL DEFAULT 'pending'
        )
        """,
    )
    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS vp_assignments (
            voyage_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            berth_id TEXT,
            etb TEXT,
            etd TEXT,
            wait_min REAL NOT NULL DEFAULT 0,
            yard_penalty REAL NOT NULL DEFAULT 0,
            score REAL NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'or',
            locked INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """,
    )
    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS vp_plan_runs (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            horizon_hours INTEGER NOT NULL DEFAULT 48,
            objective TEXT NOT NULL,
            constraints_json TEXT NOT NULL DEFAULT '{}',
            total_wait_min REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'done',
            agent_summary TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """,
    )
    _exec(cursor, "CREATE INDEX IF NOT EXISTS idx_vp_voyages_eta ON vp_voyages(tenant_id, eta)")

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS interaction_stats (
            id SERIAL PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            user_id TEXT NOT NULL DEFAULT 'default',
            session_count INTEGER DEFAULT 0,
            message_count INTEGER DEFAULT 0,
            last_active_at TIMESTAMP
        )
        """,
    )
    _exec(
        cursor,
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_interaction_tenant_user ON interaction_stats(tenant_id, user_id)",
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS provider_usage (
            id SERIAL PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            provider TEXT NOT NULL,
            model TEXT NOT NULL DEFAULT '',
            tokens_in INTEGER DEFAULT 0,
            tokens_out INTEGER DEFAULT 0,
            created_at TIMESTAMP
        )
        """,
    )
    _exec(cursor, "CREATE INDEX IF NOT EXISTS idx_provider_usage_tenant ON provider_usage(tenant_id)")
    _exec(cursor, "CREATE INDEX IF NOT EXISTS idx_provider_usage_created ON provider_usage(created_at DESC)")

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS evolution_events (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            user_id TEXT NOT NULL DEFAULT 'default',
            source TEXT NOT NULL,
            signal TEXT NOT NULL,
            payload_json TEXT DEFAULT '{}',
            weight REAL NOT NULL DEFAULT 1.0,
            created_at TEXT NOT NULL
        )
        """,
    )
    _exec(
        cursor,
        "CREATE INDEX IF NOT EXISTS idx_evolution_events_tenant ON evolution_events(tenant_id, created_at DESC)",
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS evolution_apply_log (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            target_type TEXT NOT NULL,
            target_path TEXT NOT NULL,
            before_hash TEXT NOT NULL,
            after_hash TEXT NOT NULL,
            before_content TEXT,
            diff_summary TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'applied',
            created_at TEXT NOT NULL,
            batch_id TEXT
        )
        """,
    )
    _exec(
        cursor,
        "CREATE INDEX IF NOT EXISTS idx_evolution_apply_tenant ON evolution_apply_log(tenant_id, created_at DESC)",
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS auth_tokens (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            revoked INTEGER DEFAULT 0,
            created_at TIMESTAMP
        )
        """,
    )
    _exec(
        cursor,
        "CREATE INDEX IF NOT EXISTS idx_auth_tokens_user ON auth_tokens(user_id, expires_at DESC)",
    )

    _exec(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            email TEXT UNIQUE,
            role TEXT NOT NULL,
            api_key TEXT UNIQUE,
            created_at TIMESTAMP NOT NULL,
            last_login TIMESTAMP,
            password_hash TEXT,
            role_template_id TEXT DEFAULT 'standard'
        )
        """,
    )

    _ = org_tenant_id()

    conn.commit()
