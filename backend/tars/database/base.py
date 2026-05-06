# TARS Database Layer
# SQLite 会话、消息和记忆存储

import os
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from dataclasses import dataclass


def get_local_now():
    """获取本地时间（北京时间 UTC+8）"""
    return datetime.now(timezone(timedelta(hours=8)))


@dataclass
class Session:
    id: str
    agent_id: str = "default"
    user_id: str = "default"
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
                title TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                summary TEXT
            )
        """)

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
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                importance REAL DEFAULT 0.5,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                last_accessed TIMESTAMP,
                embedding BLOB
            )
        """)

        # 数据库迁移：为旧表添加 embedding 列
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN embedding BLOB")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # 列已存在

        # core memory 4 块固定区块（Letta 模式）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS core_memory_blocks (
                name TEXT PRIMARY KEY,
                content TEXT NOT NULL DEFAULT '',
                updated_at TEXT
            )
        """)

        DEFAULT_BLOCKS = {
            "persona": "TARS：理性、简洁、注重证据的工程助手。回答以代码/事实为主，避免空话。",
            "user_profile": "（暂未学习到用户信息）",
            "project_context": "（暂未记录项目上下文）",
            "working_principles": "（暂未累积协作准则）",
        }
        now_str = get_local_now().isoformat()
        for name, content in DEFAULT_BLOCKS.items():
            cursor.execute(
                "INSERT OR IGNORE INTO core_memory_blocks (name, content, updated_at) VALUES (?, ?, ?)",
                (name, content, now_str),
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

        conn.commit()

    def create_session(self, user_id: str = "default", title: str = "New Session") -> Session:
        session_id = str(uuid.uuid4())
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, "default", user_id, title, now, now, None)
        )
        conn.commit()

        return Session(id=session_id, user_id=user_id, title=title, created_at=now, updated_at=now)

    def get_session(self, session_id: str) -> Optional[Session]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()

        if row:
            return Session(
                id=row[0],
                agent_id=row[1],
                user_id=row[2],
                title=row[3],
                created_at=datetime.fromisoformat(row[4]),
                updated_at=datetime.fromisoformat(row[5]),
                summary=row[6]
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
                timestamp=datetime.fromisoformat(row[4])
            ))

        return messages

    def list_sessions(self, user_id: str = "default", limit: int = 50) -> List[Session]:
        """按 updated_at 倒序返回会话列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
            (user_id, limit),
        )
        sessions = []
        for row in cursor.fetchall():
            sessions.append(Session(
                id=row[0],
                agent_id=row[1],
                user_id=row[2],
                title=row[3],
                created_at=datetime.fromisoformat(row[4]) if isinstance(row[4], str) else row[4],
                updated_at=datetime.fromisoformat(row[5]) if isinstance(row[5], str) else row[5],
                summary=row[6],
            ))
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """删除会话及关联消息"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
        if not cursor.fetchone():
            return False
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return True

    def update_session_title(self, session_id: str, title: str) -> bool:
        """更新会话标题"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
        if not cursor.fetchone():
            return False
        now = get_local_now()
        cursor.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, session_id),
        )
        conn.commit()
        return True

    def add_memory(
        self,
        content: str,
        category: str = "general",
        importance: float = 0.5,
        embedding: bytes = None,
        source: str = "conversation"
    ) -> Memory:
        memory_id = str(uuid.uuid4())
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO memories (id, content, category, importance, created_at, updated_at, last_accessed, embedding, access_count, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (memory_id, content, category, importance, now, now, None, embedding, 0, source)
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
            importance=importance,
            created_at=now,
            updated_at=now
        )

    def search_memories(self, query: str, limit: int = 5) -> List[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()

        # 转义 FTS5 特殊字符，防止 SQL 注入和语法错误
        # 需要转义的字符: " * ^ - : ( )
        safe_query = query.replace('"', ' ').replace('*', ' ').replace('^', ' ').replace(':', ' ').replace('(', ' ').replace(')', ' ').replace('-', ' ').strip()
        if not safe_query:
            return []

        # 简化查询：如果完全匹配失败，使用前缀匹配
        try:
            cursor.execute("""
                SELECT m.id, m.content, m.category, m.importance, m.created_at, m.updated_at, m.last_accessed
                FROM memories m
                JOIN memories_fts fts ON m.rowid = fts.rowid
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (safe_query, limit))
        except sqlite3.OperationalError:
            # 如果 FTS 查询失败，尝试简单 LIKE 查询
            cursor.execute("""
                SELECT id, content, category, importance, created_at, updated_at, last_accessed
                FROM memories
                WHERE content LIKE ?
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
            """, (f"%{query}%", limit))

        memories = []
        for row in cursor.fetchall():
            memories.append(Memory(
                id=row[0],
                content=row[1],
                category=row[2],
                importance=row[3],
                created_at=datetime.fromisoformat(row[4]),
                updated_at=datetime.fromisoformat(row[5]),
                last_accessed=datetime.fromisoformat(row[6]) if row[6] else None
            ))

        for mem in memories:
            self._update_memory_access(mem.id)

        return memories

    def get_memories_by_category(self, category: str, limit: int = 10) -> List[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, content, category, importance, created_at, updated_at, last_accessed
            FROM memories
            WHERE category = ?
            ORDER BY importance DESC, updated_at DESC
            LIMIT ?
        """, (category, limit))

        memories = []
        for row in cursor.fetchall():
            memories.append(Memory(
                id=row[0],
                content=row[1],
                category=row[2],
                importance=row[3],
                created_at=datetime.fromisoformat(row[4]),
                updated_at=datetime.fromisoformat(row[5]),
                last_accessed=datetime.fromisoformat(row[6]) if row[6] else None
            ))

        return memories

    def get_recent_memories(self, limit: int = 20) -> List[Memory]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, content, category, importance, created_at, updated_at, last_accessed
            FROM memories
            ORDER BY updated_at DESC
            LIMIT ?
        """, (limit,))

        memories = []
        for row in cursor.fetchall():
            memories.append(Memory(
                id=row[0],
                content=row[1],
                category=row[2],
                importance=row[3],
                created_at=datetime.fromisoformat(row[4]),
                updated_at=datetime.fromisoformat(row[5]),
                last_accessed=datetime.fromisoformat(row[6]) if row[6] else None
            ))

        return memories

    def update_memory(self, memory_id: str, content: str, importance: float = None):
        now = get_local_now()

        conn = self._get_conn()
        cursor = conn.cursor()

        if importance is not None:
            cursor.execute("""
                UPDATE memories
                SET content = ?, importance = ?, updated_at = ?
                WHERE id = ?
            """, (content, importance, now, memory_id))
        else:
            cursor.execute("""
                UPDATE memories
                SET content = ?, updated_at = ?
                WHERE id = ?
            """, (content, now, memory_id))

        cursor.execute("""
            UPDATE memories_fts
            SET content = ?
            WHERE rowid = (SELECT rowid FROM memories WHERE id = ?)
        """, (content, memory_id))

        conn.commit()

    def reinforce_memory(self, memory_id: str, importance_delta: float = 0.02):
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
            WHERE id = ?
            """,
            (now, importance_delta, memory_id),
        )
        conn.commit()

    def get_all_memories_with_metadata(self):
        """返回 (Memory, embedding_blob, last_accessed_iso, importance, source) 列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, content, category, importance, created_at, updated_at, embedding, last_accessed, source FROM memories"
        )
        results = []
        for row in cursor.fetchall():
            mem = Memory(
                id=row[0], content=row[1], category=row[2], importance=row[3],
                created_at=row[4], updated_at=row[5],
            )
            last_accessed_str = str(row[7]) if row[7] else (str(row[4]) if row[4] else "")
            results.append((mem, row[6], last_accessed_str, row[3] or 0.5, row[8] or "conversation"))
        return results

    def delete_memory(self, memory_id: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()

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
            return CronJob(
                id=row[0],
                user_id=row[1],
                name=row[2],
                description=row[3],
                cron_expression=row[4],
                task_type=row[5],
                task_config=row[6],
                enabled=bool(row[7]),
                created_at=datetime.fromisoformat(row[8]),
                updated_at=datetime.fromisoformat(row[9]),
                last_run=datetime.fromisoformat(row[10]) if row[10] else None,
                next_run=datetime.fromisoformat(row[11]) if row[11] else None
            )
        return None

    def get_user_cronjobs(self, user_id: str) -> List[CronJob]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cronjobs WHERE user_id = ?", (user_id,))

        cronjobs = []
        for row in cursor.fetchall():
            cronjobs.append(CronJob(
                id=row[0],
                user_id=row[1],
                name=row[2],
                description=row[3],
                cron_expression=row[4],
                task_type=row[5],
                task_config=row[6],
                enabled=bool(row[7]),
                created_at=datetime.fromisoformat(row[8]),
                updated_at=datetime.fromisoformat(row[9]),
                last_run=datetime.fromisoformat(row[10]) if row[10] else None,
                next_run=datetime.fromisoformat(row[11]) if row[11] else None
            ))
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
