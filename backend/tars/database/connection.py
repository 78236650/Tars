# TARS Database Connection
# 连接管理与 Schema 初始化（从 base.py 拆分出来）

import os
import json
import sqlite3
from typing import Optional

from tars.database.driver import (
    DbConnection,
    create_connection_factory,
    detect_dialect,
    parse_database_url,
)


class ConnectionManager:
    """管理 SQLite/Postgres 连接与建表，被 Database 门面持有。"""

    def __init__(self, db_path: Optional[str] = None):
        self.database_url = parse_database_url(db_path)
        self.db_path = self.database_url
        self.dialect = detect_dialect(self.database_url)
        self._factory = create_connection_factory(self.database_url)
        self._conn: Optional[DbConnection] = None
        self.init_schema()

    def get_conn(self) -> DbConnection:
        """获取数据库连接，保持连接打开用于内存数据库与连接池。"""
        if self._conn is None:
            self._conn = self._factory.get_conn()
        return self._conn

    def close(self):
        if self._conn:
            self._factory.release(self._conn)
            self._conn = None

    def init_schema(self):
        """初始化数据库表（从 base.py _init_db 迁出）"""
        if self.dialect == "postgres":
            from tars.database.connection_pg import init_schema_postgres

            init_schema_postgres(self.get_conn())
            return

        conn = self.get_conn()
        cursor = conn.cursor()

        cursor.execute("""
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
        """)

        try:
            cursor.execute("ALTER TABLE sessions ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'")
        except sqlite3.OperationalError:
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        # v4.3.0: messages metadata_json 列（用于存储 reasoning_content 等扩展信息）
        try:
            cursor.execute("ALTER TABLE messages ADD COLUMN metadata_json TEXT")
        except sqlite3.OperationalError:
            pass  # 列已存在

        # v5.0.1: sessions metadata_json 列（DeepSeek thinking mode）
        try:
            cursor.execute("ALTER TABLE sessions ADD COLUMN metadata_json TEXT")
        except sqlite3.OperationalError:
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                importance REAL DEFAULT 0.5,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                last_accessed TIMESTAMP,
                embedding BLOB
            )
        """)

        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'")
        except sqlite3.OperationalError:
            pass

        # 数据库迁移：为旧表添加 embedding 列
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN embedding BLOB")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # 列已存在

        # v4.0.0: 记忆 scope 字段 (private | shared)
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN scope TEXT NOT NULL DEFAULT 'private'")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # 列已存在

        # v5.0: per-user private memories within single org
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN user_id TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # v4.0.0: 记忆 access_count 字段（访问计数）
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN access_count INTEGER DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # v4.1.0: source 字段
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN source TEXT NOT NULL DEFAULT 'conversation'")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # v4.1.4: 事件时间/实体引用/置顶/压缩链/记忆类型
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN event_time TIMESTAMP")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN entity_refs TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN pinned INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN compressed_from TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN memory_type TEXT NOT NULL DEFAULT 'episodic'")
        except sqlite3.OperationalError:
            pass

        # v4.2.0: KB promotion 字段
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN promotion_group_id TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN kb_doc_id TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN kb_promotion_status TEXT")
        except sqlite3.OperationalError:
            pass

        # 全文检索虚拟表
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content, category, content=memories, content_rowid=rowid
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS core_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # v3/v5: Letta-style core memory blocks (per-user within org)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS core_memory_blocks (
                name TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT 'org_default',
                user_id TEXT NOT NULL DEFAULT 'default',
                content TEXT NOT NULL DEFAULT '',
                updated_at TEXT,
                UNIQUE(tenant_id, user_id, name)
            )
        """)
        for col_def in [
            ("tenant_id", "TEXT NOT NULL DEFAULT 'org_default'"),
            ("user_id", "TEXT NOT NULL DEFAULT 'default'"),
        ]:
            try:
                cursor.execute(
                    f"ALTER TABLE core_memory_blocks ADD COLUMN {col_def[0]} {col_def[1]}"
                )
            except sqlite3.OperationalError:
                pass

        from tars.database.models import get_local_now

        _default_blocks = {
            "persona": (
                "TARS：理性、简洁、注重证据的工程助手。回答以代码/事实为主，避免空话。"
            ),
            "user_profile": "（暂未学习到用户信息）",
            "project_context": "（暂未记录项目上下文）",
            "working_principles": "（暂未累积协作准则）",
        }
        _blocks_now = get_local_now().isoformat()
        for _block_name, _block_content in _default_blocks.items():
            cursor.execute(
                """
                INSERT OR IGNORE INTO core_memory_blocks
                (name, tenant_id, user_id, content, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (_block_name, "org_default", "default", _block_content, _blocks_now),
            )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        cursor.execute("""
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
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions_metadata (
                session_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (session_id, key)
            )
        """)

        cursor.execute("""
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
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dead_letters (
                id TEXT PRIMARY KEY,
                op TEXT NOT NULL,
                error TEXT NOT NULL,
                session_id TEXT,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
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
        """)

        cursor.execute("""
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
        """)

        cursor.execute("""
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
        """)

        cursor.execute("""
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
                kb_doc_id TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wiki_pages (
                page_name TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                title TEXT,
                summary TEXT,
                source_memory_ids TEXT,
                source_type TEXT NOT NULL DEFAULT 'manual',
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                PRIMARY KEY (tenant_id, page_name)
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_wiki_pages_tenant_memory "
            "ON wiki_pages(tenant_id, source_memory_ids)"
        )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kb_chunks (
                id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                tokens INTEGER DEFAULT 0,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (doc_id) REFERENCES document_files(id)
            )
        """)

        cursor.execute("""
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
        """)

        try:
            cursor.execute("ALTER TABLE kb_documents ADD COLUMN source_type TEXT NOT NULL DEFAULT 'upload'")
        except sqlite3.OperationalError:
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_profiles (
                id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                keywords TEXT NOT NULL DEFAULT '[]',
                topics TEXT NOT NULL DEFAULT '[]',
                language TEXT NOT NULL DEFAULT 'unknown',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (doc_id) REFERENCES kb_documents(id)
            )
        """)

        cursor.execute("""
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
        """)

        cursor.execute("""
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
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminder_notifications_user_triggered
            ON reminder_notifications(user_id, triggered_at DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminder_notifications_job_triggered
            ON reminder_notifications(job_id, triggered_at DESC)
        """)

        cursor.execute("""
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
        """)

        cursor.execute("""
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
        """)

        # 将旧 custom_models 一次性迁移为 endpoints（仅当 endpoints 为空时）
        try:
            cursor.execute("SELECT COUNT(*) FROM endpoints")
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "SELECT id, name, base_url, api_key, model, is_enabled, created_at, updated_at FROM custom_models"
                )
                for row in cursor.fetchall():
                    mid, name, base_url, api_key, model, is_en, cat, uat = row
                    models_json = json.dumps([model], ensure_ascii=False)
                    cursor.execute("""
                        INSERT OR IGNORE INTO endpoints (id, name, base_url, api_key, models, enabled, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (mid, name, base_url, api_key, models_json, is_en or 1, cat, uat))
        except sqlite3.OperationalError:
            pass

        # === v2.2 记忆认知架构新表 ===

        cursor.execute("""
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
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_entity_links (
                memory_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (memory_id, entity_id, relation)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_relations (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                tenant_id   TEXT NOT NULL,
                from_entity TEXT NOT NULL,
                to_entity   TEXT NOT NULL,
                predicate   TEXT NOT NULL,
                confidence  REAL DEFAULT 0.7,
                created_at  TEXT NOT NULL,
                PRIMARY KEY (tenant_id, from_entity, to_entity, predicate)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entity_aliases (
                entity_id TEXT NOT NULL,
                alias TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'extraction',
                created_at TEXT NOT NULL,
                PRIMARY KEY (entity_id, alias)
            )
        """)

        cursor.execute("""
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
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_tree_bindings (
                node_id TEXT NOT NULL,
                memory_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (node_id, memory_id)
            )
        """)

        try:
            cursor.execute("ALTER TABLE memory_tree_nodes ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'")
        except Exception:
            pass

        # v4.4.0 多 Agent 编排记忆
        cursor.execute("""
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
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_task_outputs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                subtask TEXT NOT NULL,
                output TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'done',
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_collaboration_ctx (
                task_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (task_id, key)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_outputs_task ON agent_task_outputs(task_id)")

        # v4.5.0 船舶进出港计划（拟真）
        cursor.execute("""
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
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vp_vessels (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                name TEXT NOT NULL,
                imo TEXT,
                length_m REAL NOT NULL,
                draft_m REAL NOT NULL,
                priority INTEGER NOT NULL DEFAULT 0
            )
        """)
        cursor.execute("""
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
        """)
        cursor.execute("""
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
        """)
        cursor.execute("""
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
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vp_voyages_eta ON vp_voyages(tenant_id, eta)")

        # v3.0 交互统计
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interaction_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                user_id TEXT NOT NULL DEFAULT 'default',
                session_count INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                last_active_at TIMESTAMP
            )
        """)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_interaction_tenant_user ON interaction_stats(tenant_id, user_id)")

        # v4.0 provider_usage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS provider_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                provider TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                created_at TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_provider_usage_tenant ON provider_usage(tenant_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_provider_usage_created ON provider_usage(created_at DESC)")

        # v5.1.0: per-user usage tracking
        try:
            cursor.execute("ALTER TABLE provider_usage ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass

        # v5.1.0: Run 生命周期 — 一次 Agent 执行过程的状态管理
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                status TEXT NOT NULL DEFAULT 'queued',
                trace_id TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                tool_calls_count INTEGER NOT NULL DEFAULT 0,
                tokens_in INTEGER NOT NULL DEFAULT 0,
                tokens_out INTEGER NOT NULL DEFAULT 0
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_session ON runs(session_id, started_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_user ON runs(user_id, tenant_id, started_at DESC)")

        # v4.2.0: Evolution events + apply audit
        cursor.execute("""
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
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evolution_events_tenant ON evolution_events(tenant_id, created_at DESC)")

        cursor.execute("""
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
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evolution_apply_tenant ON evolution_apply_log(tenant_id, created_at DESC)")
        try:
            cursor.execute("ALTER TABLE evolution_apply_log ADD COLUMN batch_id TEXT")
        except Exception:
            pass

        # v5.0: JWT access token registry (jti revocation)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth_tokens (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                revoked INTEGER DEFAULT 0,
                created_at TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_auth_tokens_user
            ON auth_tokens(user_id, expires_at DESC)
        """)

        # BI / InsightForge (bi_datasources + profile/metrics; INS-2 migrations add qlog/adoptions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bi_datasources (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                db_type TEXT NOT NULL,
                connection_url TEXT NOT NULL,
                readonly INTEGER DEFAULT 1,
                schema_snapshot TEXT DEFAULT '{}',
                schema_annotations TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                connection_config_json TEXT DEFAULT '{}'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insight_profile_runs (
                id TEXT PRIMARY KEY,
                datasource_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                capability_version TEXT NOT NULL,
                status TEXT NOT NULL,
                budget_json TEXT NOT NULL,
                progress_json TEXT NOT NULL DEFAULT '{}',
                insight_snapshot_json TEXT,
                knowledge_doc_id TEXT,
                error TEXT,
                started_at TEXT,
                finished_at TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insight_metrics (
                id TEXT PRIMARY KEY,
                datasource_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                metric_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                definition TEXT NOT NULL,
                sql_template TEXT DEFAULT '',
                tables_json TEXT DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'draft',
                source TEXT NOT NULL DEFAULT 'profile',
                confidence REAL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                superseded_by TEXT
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_insight_metrics_ds "
            "ON insight_metrics(datasource_id, tenant_id)"
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_insight_metrics_key_ver "
            "ON insight_metrics(datasource_id, tenant_id, metric_key, version)"
        )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skills_v3 (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                source TEXT NOT NULL,
                dir_path TEXT NOT NULL,
                has_pdca INTEGER DEFAULT 0,
                has_scripts INTEGER DEFAULT 0,
                permissions TEXT DEFAULT '[]',
                granted_permissions TEXT DEFAULT '[]',
                installed_at TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                scope TEXT DEFAULT 'org'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                goal TEXT NOT NULL,
                workspace_path TEXT NOT NULL,
                workspace_source TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                current_step INTEGER DEFAULT 0,
                total_steps INTEGER DEFAULT 0,
                artifacts TEXT,
                output_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                error_message TEXT,
                skill_id TEXT,
                pdca_ref TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_steps (
                task_id TEXT NOT NULL,
                step_order INTEGER NOT NULL,
                description TEXT NOT NULL,
                tool TEXT,
                arguments TEXT,
                verify_type TEXT,
                verify_expected TEXT,
                verify_msg TEXT,
                expected_artifacts TEXT,
                PRIMARY KEY (task_id, step_order)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_cases (
                case_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                user_id TEXT NOT NULL DEFAULT 'default',
                session_id TEXT,
                task_description TEXT NOT NULL,
                task_intent TEXT DEFAULT '',
                tools_used TEXT DEFAULT '[]',
                tool_results TEXT DEFAULT '[]',
                skill_id TEXT,
                subagent TEXT,
                success INTEGER NOT NULL DEFAULT 1,
                feedback_score REAL DEFAULT 0.0,
                distilled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_cases_tenant "
            "ON agent_cases(tenant_id, created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_cases_distilled "
            "ON agent_cases(tenant_id, distilled, success)"
        )

        # knowledge schema tables preserved in-place, module removed

        conn.commit()

        # v5.0.5/P4: ordered, versioned migrations on top of the idempotent base.
        from tars.database.migrations import apply_migrations

        apply_migrations(conn, dialect="sqlite")
