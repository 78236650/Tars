# TARS Database Connection
# 连接管理与 Schema 初始化（从 base.py 拆分出来）

import os
import json
import sqlite3
from typing import Optional


class ConnectionManager:
    """管理 SQLite 连接与建表，被 Database 门面持有。"""

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            data_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
            )
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "tars.db")

        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self.dialect: str = "sqlite"
        self.init_schema()

    def get_conn(self) -> sqlite3.Connection:
        """获取数据库连接，保持连接打开用于内存数据库"""
        if self._conn is None:
            busy_ms = int(os.environ.get("TARS_SQLITE_BUSY_MS", "15000"))
            self._conn = sqlite3.connect(
                self.db_path, check_same_thread=False, timeout=busy_ms / 1000.0
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute(f"PRAGMA busy_timeout={busy_ms}")
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def init_schema(self):
        """初始化数据库表（从 base.py _init_db 迁出）"""
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

        conn.commit()
