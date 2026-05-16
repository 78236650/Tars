# TARS Database Layer
# SQLite 会话、消息和记忆存储

import os
import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


def get_local_now():
    """获取本地时间（北京时间 UTC+8）"""
    return datetime.now(timezone(timedelta(hours=8)))


def _parse_db_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


@dataclass
class Session:
    id: str
    agent_id: str = "default"
    user_id: str = "default"
    tenant_id: str = "default"
    title: str = "New Session"
    created_at: datetime = None
    updated_at: datetime = None
    summary: Optional[str] = None


@dataclass
class Message:
    id: str
    session_id: str
    role: str  # user, assistant, tool, system
    content: str
    timestamp: datetime = None


@dataclass
class Memory:
    id: str
    content: str
    category: str  # user_preference, project_record, important_decision, general
    tenant_id: str = "default"
    importance: float = 0.5  # 0-1
    created_at: datetime = None
    updated_at: datetime = None
    last_accessed: Optional[datetime] = None


@dataclass
class CronJob:
    id: str
    user_id: str
    name: str
    description: Optional[str]
    cron_expression: str
    task_type: str  # prompt, delegate, reminder
    task_config: str  # JSON 配置
    enabled: bool = True
    created_at: datetime = None
    updated_at: datetime = None
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None


@dataclass
class ReminderNotification:
    id: str
    user_id: str
    job_id: str
    session_id: Optional[str]
    task_name: str
    message: str
    delivery_status: str
    error_message: Optional[str] = None
    summary_logs: List[Dict[str, Any]] = None
    is_read: bool = False
    triggered_at: datetime = None
    read_at: Optional[datetime] = None
    created_at: datetime = None
    updated_at: datetime = None


@dataclass
class Transcription:
    id: str
    user_id: str
    file_path: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[float] = None
    language: Optional[str] = None
    status: str = "pending"
    transcript: Optional[str] = None
    segments: Optional[str] = None
    summary: Optional[str] = None
    summary_type: Optional[str] = None
    key_points: Optional[str] = None
    model_used: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    approved_at: Optional[str] = None
    knowledge_doc_id: Optional[str] = None


class Database:
    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "tars.db")

        self.db_path = db_path
        self._conn = None
        self._init_db()
    
    def _get_conn(self):
        """获取数据库连接，保持连接打开用于内存数据库"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn
    
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_conn()
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

        # core memory 4 块固定区块（Letta 模式）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS core_memory_blocks (
                tenant_id TEXT NOT NULL DEFAULT 'default',
                name TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                updated_at TEXT,
                PRIMARY KEY (tenant_id, name)
            )
        """)

        cursor.execute("PRAGMA table_info(core_memory_blocks)")
        core_cols = cursor.fetchall()
        core_pk = [row[1] for row in core_cols if row[5] > 0]
        if core_cols and core_pk == ["name"]:
            cursor.execute("ALTER TABLE core_memory_blocks RENAME TO core_memory_blocks_legacy")
            cursor.execute("""
                CREATE TABLE core_memory_blocks (
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    name TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    updated_at TEXT,
                    PRIMARY KEY (tenant_id, name)
                )
            """)
            cursor.execute("""
                INSERT INTO core_memory_blocks (tenant_id, name, content, updated_at)
                SELECT 'default', name, content, updated_at
                FROM core_memory_blocks_legacy
            """)
            cursor.execute("DROP TABLE core_memory_blocks_legacy")

        DEFAULT_BLOCKS = {
            "persona": "TARS：理性、简洁、注重证据的工程助手。回答以代码/事实为主，避免空话。",
            "user_profile": "（暂未学习到用户信息）",
            "project_context": "（暂未记录项目上下文）",
            "working_principles": "（暂未累积协作准则）",
        }
        now_str = get_local_now().isoformat()
        for name, content in DEFAULT_BLOCKS.items():
            cursor.execute(
                """
                INSERT OR IGNORE INTO core_memory_blocks (name, tenant_id, content, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, "default", content, now_str),
            )

        # memories 表迁移：access_count + source
        for col_name, col_type in [
            ("access_count", "INTEGER DEFAULT 0"),
            ("source", "TEXT DEFAULT 'conversation'"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE memories ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass  # 列已存在

        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content,
                category,
                content='memories',
                content_rowid='rowid'
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
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                last_run TIMESTAMP,
                next_run TIMESTAMP
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
                importance REAL DEFAULT 0.5,
                last_accessed TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)")
        # FTS5 表用于别名搜索
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS entities_aliases_fts USING fts5(
                aliases, content='entities', content_rowid='rowid'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_entity TEXT NOT NULL,
                to_entity TEXT NOT NULL,
                predicate TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                source_memory_id INTEGER,
                created_at TEXT NOT NULL,
                UNIQUE(from_entity, to_entity, predicate)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS working_contexts (
                tenant_id TEXT NOT NULL DEFAULT 'default',
                session_id TEXT NOT NULL,
                focus_entities TEXT DEFAULT '[]',
                current_intent TEXT DEFAULT 'unknown',
                intent_confidence REAL DEFAULT 0,
                open_threads TEXT DEFAULT '[]',
                active_skills TEXT DEFAULT '[]',
                last_scene_snapshot TEXT DEFAULT '{}',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, session_id)
            )
        """)

        cursor.execute("PRAGMA table_info(working_contexts)")
        wc_cols = cursor.fetchall()
        wc_pk = [row[1] for row in wc_cols if row[5] > 0]
        if wc_cols and wc_pk == ["session_id"]:
            cursor.execute("ALTER TABLE working_contexts RENAME TO working_contexts_legacy")
            cursor.execute("""
                CREATE TABLE working_contexts (
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    session_id TEXT NOT NULL,
                    focus_entities TEXT DEFAULT '[]',
                    current_intent TEXT DEFAULT 'unknown',
                    intent_confidence REAL DEFAULT 0,
                    open_threads TEXT DEFAULT '[]',
                    active_skills TEXT DEFAULT '[]',
                    last_scene_snapshot TEXT DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, session_id)
                )
            """)
            cursor.execute("""
                INSERT INTO working_contexts (
                    tenant_id, session_id, focus_entities, current_intent,
                    intent_confidence, open_threads, active_skills,
                    last_scene_snapshot, updated_at
                )
                SELECT
                    'default', session_id, focus_entities, current_intent,
                    intent_confidence, open_threads, active_skills,
                    last_scene_snapshot, updated_at
                FROM working_contexts_legacy
            """)
            cursor.execute("DROP TABLE working_contexts_legacy")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dead_letter_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                op TEXT NOT NULL,
                error TEXT,
                retry_count INTEGER DEFAULT 0,
                session_id TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # v2.2 memories 表加列
        # === v2.4 任务自动化 ===
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
                error_message TEXT
            )
            """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL REFERENCES tasks(id),
                step_order INTEGER NOT NULL,
                description TEXT NOT NULL,
                tool TEXT NOT NULL,
                arguments TEXT,
                verify_type TEXT,
                verify_expected TEXT,
                verify_msg TEXT,
                expected_artifacts TEXT,
                status TEXT DEFAULT 'pending',
                result TEXT,
                error TEXT,
                retries INTEGER DEFAULT 0,
                started_at TEXT,
                completed_at TEXT
            )
            """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_steps_task ON task_steps(task_id, step_order)")

        # === v2.5 Agent Skills ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skills_v3 (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'local',
                dir_path TEXT NOT NULL,
                has_pdca INTEGER DEFAULT 0,
                has_scripts INTEGER DEFAULT 0,
                permissions TEXT DEFAULT '[]',
                granted_permissions TEXT DEFAULT '[]',
                installed_at TEXT NOT NULL,
                enabled INTEGER DEFAULT 1
            )
        """)

        # v2.5 tasks 表加列
        for col, coltype in [("skill_id", "TEXT"), ("pdca_ref", "TEXT")]:
            try:
                cursor.execute(f"ALTER TABLE tasks ADD COLUMN {col} {coltype}")
            except sqlite3.OperationalError:
                pass
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_skill ON tasks(skill_id)")

        # === BI Analytics: 数据源表 ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bi_datasources (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                name TEXT NOT NULL,
                db_type TEXT NOT NULL,
                connection_url TEXT NOT NULL,
                readonly INTEGER DEFAULT 1,
                schema_snapshot TEXT DEFAULT '{}',
                schema_annotations TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bi_datasources_tenant ON bi_datasources(tenant_id)")

        # === Knowledge Base: 文档集合表 ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_collections (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_collections_tenant ON document_collections(tenant_id)")

        # === Knowledge Base: 文档文件表 ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_files (
                id TEXT PRIMARY KEY,
                collection_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT,
                file_type TEXT,
                chunk_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY (collection_id) REFERENCES document_collections(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_files_collection ON document_files(collection_id)")

        # === Meeting Voice Recognition: transcriptions 表 ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transcriptions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'default',
                file_path TEXT NOT NULL,
                file_name TEXT,
                file_size INTEGER,
                duration REAL,
                language TEXT,
                status TEXT DEFAULT 'pending',
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_user ON transcriptions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_status ON transcriptions(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_created ON transcriptions(created_at DESC)")

        conn.commit()

    def create_session(
        self,
        user_id: str = "default",
        title: str = "New Session",
        tenant_id: str = "default",
    ) -> Session:
        session_id = str(uuid.uuid4())
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sessions (id, agent_id, user_id, tenant_id, title, created_at, updated_at, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, "default", user_id, tenant_id, title, now, now, None),
        )
        conn.commit()

        return Session(
            id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            title=title,
            created_at=now,
            updated_at=now,
        )

    def get_session(self, session_id: str, tenant_id: str = "default") -> Optional[Session]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, agent_id, user_id, tenant_id, title, created_at, updated_at, summary
            FROM sessions
            WHERE id = ? AND tenant_id = ?
            """,
            (session_id, tenant_id),
        )
        row = cursor.fetchone()

        if row:
            return Session(
                id=row[0],
                agent_id=row[1],
                user_id=row[2],
                tenant_id=row[3],
                title=row[4],
                created_at=_parse_db_datetime(row[5]),
                updated_at=_parse_db_datetime(row[6]),
                summary=row[7],
            )
        return None

    def add_message(self, session_id: str, role: str, content: str) -> Message:
        message_id = str(uuid.uuid4())
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages VALUES (?, ?, ?, ?, ?)",
            (message_id, session_id, role, content, now)
        )

        cursor.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id)
        )
        conn.commit()

        return Message(id=message_id, session_id=session_id, role=role, content=content, timestamp=now)

    def get_messages(self, session_id: str) -> List[Message]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        )

        messages = []
        for row in cursor.fetchall():
            messages.append(Message(
                id=row[0],
                session_id=row[1],
                role=row[2],
                content=row[3],
                timestamp=_parse_db_datetime(row[4])
            ))

        return messages

    def list_sessions(
        self,
        user_id: str = "default",
        tenant_id: str = "default",
        limit: int = 50,
    ) -> List[Session]:
        """按 updated_at 倒序返回会话列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, agent_id, user_id, tenant_id, title, created_at, updated_at, summary
            FROM sessions
            WHERE user_id = ? AND tenant_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (user_id, tenant_id, limit),
        )
        sessions = []
        for row in cursor.fetchall():
            sessions.append(Session(
                id=row[0],
                agent_id=row[1],
                user_id=row[2],
                tenant_id=row[3],
                title=row[4],
                created_at=_parse_db_datetime(row[5]),
                updated_at=_parse_db_datetime(row[6]),
                summary=row[7],
            ))
        return sessions

    def delete_session(self, session_id: str, tenant_id: str = "default") -> bool:
        """删除会话及关联消息"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sessions WHERE id = ? AND tenant_id = ?", (session_id, tenant_id))
        if not cursor.fetchone():
            return False
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE id = ? AND tenant_id = ?", (session_id, tenant_id))
        conn.commit()
        return True

    def update_session_title(self, session_id: str, title: str, tenant_id: str = "default") -> bool:
        """更新会话标题"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sessions WHERE id = ? AND tenant_id = ?", (session_id, tenant_id))
        if not cursor.fetchone():
            return False
        now = get_local_now()
        cursor.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ? AND tenant_id = ?",
            (title, now, session_id, tenant_id),
        )
        conn.commit()
        return True

    def add_memory(
        self,
        content: str,
        category: str = "general",
        importance: float = 0.5,
        embedding: bytes = None,
        source: str = "conversation",
        tenant_id: str = "default",
    ) -> Memory:
        memory_id = str(uuid.uuid4())
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memories
            (id, tenant_id, content, category, importance, created_at, updated_at, last_accessed, embedding, access_count, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (memory_id, tenant_id, content, category, importance, now, now, None, embedding, 0, source),
        )

        cursor.execute(
            "INSERT INTO memories_fts(rowid, content, category) VALUES (last_insert_rowid(), ?, ?)",
            (content, category)
        )

        conn.commit()

        return Memory(
            id=memory_id,
            content=content,
            category=category,
            tenant_id=tenant_id,
            importance=importance,
            created_at=now,
            updated_at=now
        )

    @staticmethod
    def _has_cjk(text: str) -> bool:
        """检查文本是否包含 CJK 字符"""
        for ch in text:
            cp = ord(ch)
            if (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
                0x3000 <= cp <= 0x303F or 0xFF00 <= cp <= 0xFFEF or
                0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF or
                0xAC00 <= cp <= 0xD7AF):
                return True
        return False

    def search_memories(self, query: str, limit: int = 5, tenant_id: str = "default") -> List[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()

        # 转义 FTS5 特殊字符
        safe_query = query.replace('"', ' ').replace('*', ' ').replace('^', ' ')
        safe_query = safe_query.replace(':', ' ').replace('(', ' ').replace(')', ' ').replace('-', ' ').strip()
        has_cjk = self._has_cjk(query)

        memories = []
        # 1. 尝试 FTS5 搜索
        if safe_query:
            try:
                cursor.execute("""
                    SELECT m.id, m.tenant_id, m.content, m.category, m.importance, m.created_at, m.updated_at, m.last_accessed
                    FROM memories m
                    JOIN memories_fts fts ON m.rowid = fts.rowid
                    WHERE memories_fts MATCH ? AND m.tenant_id = ?
                    ORDER BY rank
                    LIMIT ?
                """, (safe_query, tenant_id, limit))
                for row in cursor.fetchall():
                    memories.append(Memory(
                        id=row[0], tenant_id=row[1], content=row[2], category=row[3],
                        importance=row[4], created_at=datetime.fromisoformat(row[5]),
                        updated_at=datetime.fromisoformat(row[6]),
                        last_accessed=datetime.fromisoformat(row[7]) if row[7] else None,
                    ))
            except sqlite3.OperationalError:
                pass

        # 2. FTS5 无结果 + 含 CJK → LIKE fallback
        if not memories and has_cjk:
            try:
                cursor.execute("""
                    SELECT id, tenant_id, content, category, importance, created_at, updated_at, last_accessed
                    FROM memories WHERE tenant_id = ? AND content LIKE ? ORDER BY importance DESC, updated_at DESC LIMIT ?
                """, (tenant_id, f"%{query}%", limit))
                for row in cursor.fetchall():
                    memories.append(Memory(
                        id=row[0], tenant_id=row[1], content=row[2], category=row[3],
                        importance=row[4], created_at=datetime.fromisoformat(row[5]),
                        updated_at=datetime.fromisoformat(row[6]),
                        last_accessed=datetime.fromisoformat(row[7]) if row[7] else None,
                    ))
            except sqlite3.OperationalError:
                pass

        # 3. 空结果兜底：通用 LIKE
        if not memories:
            try:
                cursor.execute("""
                    SELECT id, tenant_id, content, category, importance, created_at, updated_at, last_accessed
                    FROM memories WHERE tenant_id = ? AND content LIKE ? ORDER BY importance DESC, updated_at DESC LIMIT ?
                """, (tenant_id, f"%{query}%", limit))
                for row in cursor.fetchall():
                    memories.append(Memory(
                        id=row[0], tenant_id=row[1], content=row[2], category=row[3],
                        importance=row[4], created_at=datetime.fromisoformat(row[5]),
                        updated_at=datetime.fromisoformat(row[6]),
                        last_accessed=datetime.fromisoformat(row[7]) if row[7] else None,
                    ))
            except sqlite3.OperationalError:
                pass

        for mem in memories:
            self._update_memory_access(mem.id)

        return memories

    def get_memories_by_category(self, category: str, limit: int = 10, tenant_id: str = "default") -> List[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, tenant_id, content, category, importance, created_at, updated_at, last_accessed
            FROM memories
            WHERE tenant_id = ? AND category = ?
            ORDER BY importance DESC, updated_at DESC
            LIMIT ?
        """, (tenant_id, category, limit))

        memories = []
        for row in cursor.fetchall():
            memories.append(Memory(
                id=row[0],
                tenant_id=row[1],
                content=row[2],
                category=row[3],
                importance=row[4],
                created_at=datetime.fromisoformat(row[5]),
                updated_at=datetime.fromisoformat(row[6]),
                last_accessed=datetime.fromisoformat(row[7]) if row[7] else None
            ))

        return memories

    def get_recent_memories(self, limit: int = 20, tenant_id: str = "default") -> List[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, tenant_id, content, category, importance, created_at, updated_at, last_accessed
            FROM memories
            WHERE tenant_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
        """, (tenant_id, limit))

        memories = []
        for row in cursor.fetchall():
            memories.append(Memory(
                id=row[0],
                tenant_id=row[1],
                content=row[2],
                category=row[3],
                importance=row[4],
                created_at=datetime.fromisoformat(row[5]),
                updated_at=datetime.fromisoformat(row[6]),
                last_accessed=datetime.fromisoformat(row[7]) if row[7] else None
            ))

        return memories

    def update_memory(self, memory_id: str, content: str, importance: float = None, tenant_id: str = "default"):
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()

        if importance is not None:
            cursor.execute("""
                UPDATE memories
                SET content = ?, importance = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ?
            """, (content, importance, now, memory_id, tenant_id))
        else:
            cursor.execute("""
                UPDATE memories
                SET content = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ?
            """, (content, now, memory_id, tenant_id))

        cursor.execute("""
            UPDATE memories_fts
            SET content = ?
            WHERE rowid = (SELECT rowid FROM memories WHERE id = ? AND tenant_id = ?)
        """, (content, memory_id, tenant_id))

        conn.commit()

    def reinforce_memory(self, memory_id: str, importance_delta: float = 0.02, tenant_id: str = "default"):
        """命中召回：access_count+1, last_accessed=now, importance 微增"""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = get_local_now()
        cursor.execute(
            """
            UPDATE memories
            SET access_count = COALESCE(access_count, 0) + 1,
                last_accessed = ?,
                importance = MIN(1.0, COALESCE(importance, 0.5) + ?)
            WHERE id = ? AND tenant_id = ?
            """,
            (now, importance_delta, memory_id, tenant_id),
        )
        conn.commit()

    def get_all_memories_with_metadata(self, tenant_id: str = "default"):
        """返回 (Memory, embedding_blob, last_accessed_iso, importance, source) 列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tenant_id, content, category, importance, created_at, updated_at, embedding, last_accessed, source
            FROM memories WHERE tenant_id = ?
            """,
            (tenant_id,),
        )
        results = []
        for row in cursor.fetchall():
            mem = Memory(
                id=row[0], tenant_id=row[1], content=row[2], category=row[3], importance=row[4],
                created_at=row[5], updated_at=row[6],
            )
            last_accessed_str = str(row[8]) if row[8] else (str(row[5]) if row[5] else "")
            results.append((mem, row[7], last_accessed_str, row[4] or 0.5, row[9] or "conversation"))
        return results

    def delete_memory(self, memory_id: str, tenant_id: str = "default"):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memories WHERE id = ? AND tenant_id = ?", (memory_id, tenant_id))
        conn.commit()

    def decay_importance(self):
        """重要性自然衰减：未被访问的记忆重要性随时间微降"""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = get_local_now()
        # 超过 24 小时未访问的记忆，importance 每日衰减 0.01，不低于 0.1
        cursor.execute("""
            UPDATE memories
            SET importance = MAX(0.1, importance - 0.01 * CAST((julianday(?) - julianday(COALESCE(last_accessed, created_at))) AS INTEGER))
            WHERE COALESCE(last_accessed, created_at) < ?
        """, (now.isoformat(), (now - timedelta(hours=24)).isoformat()))
        count = cursor.rowcount
        conn.commit()
        return count

    def cleanup_old_memories(self, min_importance: float = 0.25, max_age_days: int = 15) -> int:
        """清理过期记忆：重要性低于阈值 + 超过指定天数未访问"""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = get_local_now()
        cutoff = now - timedelta(days=max_age_days)
        cursor.execute("""
            DELETE FROM memories
            WHERE importance < ?
              AND COALESCE(last_accessed, created_at) < ?
        """, (min_importance, cutoff.isoformat()))
        deleted = cursor.rowcount
        if deleted > 0:
            # 重建 FTS 索引
            cursor.execute("DELETE FROM memories_fts")
            cursor.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
        conn.commit()
        return deleted

    def forget_core_line(self, block: str, line_contains: str, tenant_id: str = "default") -> bool:
        """从 core memory 区块中删除匹配的行"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM core_memory_blocks WHERE name = ? AND tenant_id = ?",
            (block, tenant_id),
        )
        row = cursor.fetchone()
        if not row:
            return False
        content = row[0]
        lines = content.split("\n")
        new_lines = [l for l in lines if line_contains not in l]
        if len(new_lines) == len(lines):
            return False
        new_content = "\n".join(new_lines)
        now = get_local_now().isoformat()
        cursor.execute(
            "UPDATE core_memory_blocks SET content = ?, updated_at = ? WHERE name = ? AND tenant_id = ?",
            (new_content, now, block, tenant_id),
        )
        conn.commit()
        return True

    def get_document_file(self, doc_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, collection_id, file_name, file_path, file_type, chunk_count, status, created_at FROM document_files WHERE id = ?",
            (doc_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "collection_id": row[1],
            "file_name": row[2],
            "file_path": row[3],
            "file_type": row[4],
            "chunk_count": row[5],
            "status": row[6],
            "created_at": row[7],
        }

    def delete_document_file(self, doc_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM document_files WHERE id = ?", (doc_id,))
        conn.commit()
        return cursor.rowcount > 0

    def _update_memory_access(self, memory_id: str):
        now = get_local_now()
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE memories SET last_accessed = ? WHERE id = ?",
            (now, memory_id)
        )
        conn.commit()

    def get_all_memories_with_embeddings(self) -> List[Tuple]:
        """获取所有记忆及其嵌入向量（用于语义搜索）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, content, category, importance, created_at, updated_at, last_accessed, embedding
            FROM memories
            ORDER BY updated_at DESC
        """)
        results = []
        for row in cursor.fetchall():
            mem = Memory(
                id=row[0], content=row[1], category=row[2], importance=row[3],
                created_at=datetime.fromisoformat(row[4]),
                updated_at=datetime.fromisoformat(row[5]),
                last_accessed=datetime.fromisoformat(row[6]) if row[6] else None,
            )
            results.append((mem, row[7]))  # (Memory, embedding_blob)
        return results

    # ============ CronJob 定时任务方法 ============
    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value)

    def _row_to_cronjob(self, row) -> CronJob:
        return CronJob(
            id=row[0],
            user_id=row[1],
            name=row[2],
            description=row[3],
            cron_expression=row[4],
            task_type=row[5],
            task_config=row[6],
            enabled=bool(row[7]),
            created_at=self._parse_datetime(row[8]),
            updated_at=self._parse_datetime(row[9]),
            last_run=self._parse_datetime(row[10]),
            next_run=self._parse_datetime(row[11]),
        )

    def _row_to_reminder_notification(self, row) -> ReminderNotification:
        return ReminderNotification(
            id=row[0],
            user_id=row[1],
            job_id=row[2],
            session_id=row[3],
            task_name=row[4],
            message=row[5],
            delivery_status=row[6],
            error_message=row[7],
            summary_logs=json.loads(row[8] or "[]"),
            is_read=bool(row[9]),
            triggered_at=self._parse_datetime(row[10]),
            read_at=self._parse_datetime(row[11]),
            created_at=self._parse_datetime(row[12]),
            updated_at=self._parse_datetime(row[13]),
        )

    def create_cronjob(
        self,
        user_id: str,
        name: str,
        cron_expression: str,
        task_type: str,
        task_config: str,
        description: Optional[str] = None
    ) -> CronJob:
        cronjob_id = str(uuid.uuid4())
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cronjobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cronjob_id, user_id, name, description, cron_expression,
            task_type, task_config, 1, now, now, None, None
        ))
        conn.commit()

        return CronJob(
            id=cronjob_id,
            user_id=user_id,
            name=name,
            description=description,
            cron_expression=cron_expression,
            task_type=task_type,
            task_config=task_config,
            enabled=True,
            created_at=now,
            updated_at=now
        )

    def get_cronjob(self, cronjob_id: str) -> Optional[CronJob]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cronjobs WHERE id = ?", (cronjob_id,))
        row = cursor.fetchone()

        if row:
            return self._row_to_cronjob(row)
        return None

    def get_user_cronjobs(self, user_id: str) -> List[CronJob]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM cronjobs WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )

        cronjobs = []
        for row in cursor.fetchall():
            cronjobs.append(self._row_to_cronjob(row))
        return cronjobs

    def get_enabled_cronjobs(self) -> List[CronJob]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cronjobs WHERE enabled = 1")

        cronjobs = []
        for row in cursor.fetchall():
            cronjobs.append(self._row_to_cronjob(row))
        return cronjobs

    def update_cronjob(self, cronjob_id: str, **kwargs):
        now = get_local_now()
        conn = self._get_conn()
        cursor = conn.cursor()

        updates = []
        params = []

        for key, value in kwargs.items():
            if key in ['name', 'description', 'cron_expression', 'task_type', 'task_config']:
                updates.append(f"{key} = ?")
                params.append(value)
            elif key == 'enabled':
                updates.append("enabled = ?")
                params.append(1 if value else 0)
            elif key == 'last_run':
                updates.append("last_run = ?")
                params.append(value.isoformat() if value else None)
            elif key == 'next_run':
                updates.append("next_run = ?")
                params.append(value.isoformat() if value else None)

        if updates:
            updates.append("updated_at = ?")
            params.append(now.isoformat())
            params.append(cronjob_id)
            cursor.execute(f"UPDATE cronjobs SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

    def delete_cronjob(self, cronjob_id: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cronjobs WHERE id = ?", (cronjob_id,))
        conn.commit()

    def create_reminder_notification(
        self,
        user_id: str,
        job_id: str,
        session_id: Optional[str],
        task_name: str,
        message: str,
        delivery_status: str,
        error_message: Optional[str] = None,
        summary_logs: Optional[List[Dict[str, Any]]] = None,
        triggered_at: Optional[datetime] = None,
    ) -> ReminderNotification:
        notification_id = str(uuid.uuid4())
        now = get_local_now()
        triggered = triggered_at or now

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO reminder_notifications (
                id, user_id, job_id, session_id, task_name, message, delivery_status,
                error_message, summary_logs, is_read, triggered_at, read_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                notification_id,
                user_id,
                job_id,
                session_id,
                task_name,
                message,
                delivery_status,
                error_message,
                json.dumps(summary_logs or [], ensure_ascii=False),
                0,
                triggered.isoformat(),
                None,
                now.isoformat(),
                now.isoformat(),
            ),
        )
        conn.commit()

        return ReminderNotification(
            id=notification_id,
            user_id=user_id,
            job_id=job_id,
            session_id=session_id,
            task_name=task_name,
            message=message,
            delivery_status=delivery_status,
            error_message=error_message,
            summary_logs=summary_logs or [],
            is_read=False,
            triggered_at=triggered,
            read_at=None,
            created_at=now,
            updated_at=now,
        )

    def list_reminder_notifications(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[ReminderNotification]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM reminder_notifications
            WHERE user_id = ?
            ORDER BY triggered_at DESC, created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        )
        return [self._row_to_reminder_notification(row) for row in cursor.fetchall()]

    def count_reminder_notifications(self, user_id: str) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM reminder_notifications WHERE user_id = ?",
            (user_id,),
        )
        return int(cursor.fetchone()[0])

    def count_unread_reminder_notifications(self, user_id: str) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM reminder_notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
        )
        return int(cursor.fetchone()[0])

    def get_reminder_notification(self, notification_id: str) -> Optional[ReminderNotification]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM reminder_notifications WHERE id = ?",
            (notification_id,),
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_reminder_notification(row)
        return None

    def mark_reminder_notification_read(self, notification_id: str) -> Optional[ReminderNotification]:
        notification = self.get_reminder_notification(notification_id)
        if not notification:
            return None
        if notification.is_read:
            return notification

        now = get_local_now().isoformat()
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE reminder_notifications
            SET is_read = 1, read_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, notification_id),
        )
        conn.commit()
        return self.get_reminder_notification(notification_id)

    def get_latest_reminder_notification_for_job(
        self,
        job_id: str,
    ) -> Optional[ReminderNotification]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM reminder_notifications
            WHERE job_id = ?
            ORDER BY triggered_at DESC, created_at DESC
            LIMIT 1
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_reminder_notification(row)
        return None

    # ============ v2.2 Working Context ============

    def get_working_context(self, session_id: str, tenant_id: str = "default") -> dict:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM working_contexts WHERE tenant_id = ? AND session_id = ?",
            (tenant_id, session_id),
        )
        row = cur.fetchone()
        if not row:
            return {}
        import json
        return {
            "tenant_id": row[0],
            "session_id": row[1],
            "focus_entities": json.loads(row[2] or "[]"),
            "current_intent": row[3] or "unknown",
            "intent_confidence": row[4] or 0,
            "open_threads": json.loads(row[5] or "[]"),
            "active_skills": json.loads(row[6] or "[]"),
            "last_scene_snapshot": json.loads(row[7] or "{}"),
            "updated_at": row[8],
        }

    def upsert_working_context(self, session_id: str, tenant_id: str = "default", **kwargs):
        conn = self._get_conn()
        cur = conn.cursor()
        import json
        now = get_local_now().isoformat()
        cur.execute(
            "SELECT session_id FROM working_contexts WHERE tenant_id = ? AND session_id = ?",
            (tenant_id, session_id),
        )
        exists = cur.fetchone()
        if exists:
            sets = []
            vals = []
            for k in ["focus_entities", "current_intent", "intent_confidence",
                       "open_threads", "active_skills", "last_scene_snapshot"]:
                if k in kwargs:
                    v = kwargs[k]
                    sets.append(f"{k} = ?")
                    vals.append(json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
            sets.append("updated_at = ?"); vals.append(now)
            vals.extend([tenant_id, session_id])
            cur.execute(
                f"UPDATE working_contexts SET {', '.join(sets)} WHERE tenant_id = ? AND session_id = ?",
                vals,
            )
        else:
            cur.execute(
                "INSERT INTO working_contexts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (tenant_id, session_id,
                 json.dumps(kwargs.get("focus_entities", []), ensure_ascii=False),
                 kwargs.get("current_intent", "unknown"),
                 kwargs.get("intent_confidence", 0),
                 json.dumps(kwargs.get("open_threads", []), ensure_ascii=False),
                 json.dumps(kwargs.get("active_skills", []), ensure_ascii=False),
                 json.dumps(kwargs.get("last_scene_snapshot", {}), ensure_ascii=False),
                 now),
            )
        conn.commit()

    def cleanup_working_contexts(self, max_age_hours: int = 72, tenant_id: str | None = None):
        conn = self._get_conn()
        cur = conn.cursor()
        cutoff = (get_local_now() - timedelta(hours=max_age_hours)).isoformat()
        if tenant_id is None:
            cur.execute("DELETE FROM working_contexts WHERE updated_at < ?", (cutoff,))
        else:
            cur.execute(
                "DELETE FROM working_contexts WHERE tenant_id = ? AND updated_at < ?",
                (tenant_id, cutoff),
            )
        conn.commit()

    def add_dead_letter(self, op: str, error: str, session_id: str = None):
        conn = self._get_conn()
        cur = conn.cursor()
        now = get_local_now().isoformat()
        cur.execute(
            "INSERT INTO dead_letter_queue (op, error, session_id, created_at) VALUES (?, ?, ?, ?)",
            (op, error, session_id, now),
        )
        conn.commit()

    # ============ Meeting Voice Recognition ============

    def create_transcription(
        self,
        user_id: str,
        file_path: str,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        language: Optional[str] = None,
        model_used: Optional[str] = None,
    ) -> Transcription:
        transcription_id = str(uuid.uuid4())
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO transcriptions
            (id, user_id, file_path, file_name, file_size, language, status, model_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (transcription_id, user_id, file_path, file_name, file_size, language, "pending", model_used, now),
        )
        conn.commit()

        return Transcription(
            id=transcription_id,
            user_id=user_id,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            language=language,
            status="pending",
            model_used=model_used,
            created_at=now,
        )

    def get_transcription(self, transcription_id: str) -> Optional[Transcription]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, file_path, file_name, file_size, duration, language, status,
                   transcript, segments, summary, summary_type, key_points, model_used,
                   created_at, completed_at, error_message
            FROM transcriptions WHERE id = ?
            """,
            (transcription_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_transcription(row)

    def list_transcriptions(self, user_id: str = "default", limit: int = 50, offset: int = 0) -> List[Transcription]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, file_path, file_name, file_size, duration, language, status,
                   transcript, segments, summary, summary_type, key_points, model_used,
                   created_at, completed_at, error_message
            FROM transcriptions WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        )
        return [self._row_to_transcription(row) for row in cursor.fetchall()]

    def update_transcription(self, transcription_id: str, **kwargs) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()

        allowed_fields = {
            "duration", "language", "status", "transcript", "segments",
            "summary", "summary_type", "key_points", "model_used", "error_message",
        }
        updates = []
        params = []

        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = ?")
                params.append(value)

        if not updates:
            return False

        now = get_local_now()
        updates.append("completed_at = ?")
        params.append(now)
        params.append(transcription_id)

        cursor.execute(
            f"UPDATE transcriptions SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
        return cursor.rowcount > 0

    def delete_transcription(self, transcription_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()

        # 先获取文件路径用于删除文件
        cursor.execute("SELECT file_path FROM transcriptions WHERE id = ?", (transcription_id,))
        row = cursor.fetchone()
        if not row:
            return False

        file_path = row[0]
        cursor.execute("DELETE FROM transcriptions WHERE id = ?", (transcription_id,))
        conn.commit()

        # 尝试删除关联文件
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

        return True

    def _row_to_transcription(self, row) -> Transcription:
        return Transcription(
            id=row[0],
            user_id=row[1],
            file_path=row[2],
            file_name=row[3],
            file_size=row[4],
            duration=row[5],
            language=row[6],
            status=row[7],
            transcript=row[8],
            segments=row[9],
            summary=row[10],
            summary_type=row[11],
            key_points=row[12],
            model_used=row[13],
            created_at=_parse_db_datetime(row[14]),
            completed_at=_parse_db_datetime(row[15]),
            error_message=row[16],
            approved_at=row[17] if len(row) > 17 else None,
            knowledge_doc_id=row[18] if len(row) > 18 else None,
        )
