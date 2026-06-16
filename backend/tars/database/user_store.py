# TARS Database - User Store
# 用户数据持久化存储模块

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from dataclasses import dataclass
from ..gateway.permission import UserRole
from ..security.crypto import encrypt, decrypt, decrypt_or_none, lookup_hash


@dataclass
class User:
    """用户数据模型"""
    id: str
    username: str
    email: str
    role: UserRole
    api_key: Optional[str]
    created_at: datetime
    last_login: Optional[datetime] = None
    role_template_id: Optional[str] = None


class UserStore:
    """用户数据存储管理器"""

    _PASSWORD_ALGORITHM = "pbkdf2_sha256"
    _PASSWORD_ITERATIONS = 100000
    
    def __init__(self, db):
        self.db = db
        self._init_tables()
    
    def _init_tables(self):
        """初始化用户相关数据库表"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        
        # users 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT UNIQUE,
                role TEXT NOT NULL,
                api_key TEXT UNIQUE,
                created_at TIMESTAMP NOT NULL,
                last_login TIMESTAMP,
                password_hash TEXT
            )
        """)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN role_template_id TEXT DEFAULT 'standard'")
        except Exception:
            pass
        # v5.0.5/P6: deterministic hash of api_key for indexed lookups (the
        # api_key column itself now stores an encrypted token).
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN api_key_hash TEXT")
        except Exception:
            pass
        
        # user_sessions 表 - 用户与会话关联
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id TEXT,
                session_id TEXT PRIMARY KEY,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # subagent_config 表 - 子代理配置
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subagent_config (
                user_id TEXT,
                agent_type TEXT,
                llm_model TEXT,
                llm_provider TEXT,
                temperature REAL NOT NULL DEFAULT 0.7,
                personality_weight REAL NOT NULL DEFAULT 0.5,
                enabled INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, agent_type)
            )
        """)
        
        # subagent_tasks 表 - 子代理任务记录
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subagent_tasks (
                task_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                input TEXT NOT NULL,
                output TEXT,
                status TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP
            )
        """)
        
        conn.commit()
    
    def _generate_api_key(self) -> str:
        """生成唯一的 API Key"""
        return str(uuid.uuid4()).replace("-", "")

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            self._PASSWORD_ITERATIONS,
        )
        return (
            f"{self._PASSWORD_ALGORITHM}$"
            f"{self._PASSWORD_ITERATIONS}$"
            f"{salt}$"
            f"{digest.hex()}"
        )

    def _verify_password_hash(self, password: str, password_hash: str) -> bool:
        if not password_hash:
            return False

        try:
            algorithm, iterations, salt, expected_digest = password_hash.split("$", 3)
        except ValueError:
            return False

        if algorithm != self._PASSWORD_ALGORITHM:
            return False

        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), expected_digest)
    
    def create_user(
        self,
        username: str,
        email: str,
        role: UserRole = UserRole.USER,
        password: Optional[str] = None,
    ) -> User:
        """
        创建新用户
        
        Args:
            username: 用户名
            email: 邮箱
            role: 用户角色（默认为普通用户）
            password: 用户密码（可选）
        
        Returns:
            User: 创建的用户对象
        """
        user_id = str(uuid.uuid4())
        api_key = self._generate_api_key()
        now = datetime.now(timezone(timedelta(hours=8)))
        password_hash = self._hash_password(password) if password is not None else None

        # v5.0.5/P6: store api_key encrypted at rest; keep a deterministic hash
        # for indexed lookups.
        api_key_enc = encrypt(api_key)
        api_key_h = lookup_hash(api_key)

        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users
            (id, username, email, role, api_key, api_key_hash, created_at, last_login, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, email, role.value, api_key_enc, api_key_h, now, None, password_hash)
        )
        conn.commit()

        return User(
            id=user_id,
            username=username,
            email=email,
            role=role,
            api_key=api_key,
            created_at=now
        )

    def verify_password(self, user_id: str, password: str) -> bool:
        """校验用户密码是否正确"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()

        if not row:
            return False

        return self._verify_password_hash(password, row[0])
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """通过用户ID获取用户"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            return User(
                id=row[0],
                username=row[1],
                email=row[2],
                role=UserRole(row[3]),
                api_key=decrypt_or_none(row[4]),
                created_at=datetime.fromisoformat(row[5]),
                last_login=datetime.fromisoformat(row[6]) if row[6] else None,
                role_template_id=row[8] if len(row) > 8 else None,
            )
        return None

    def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        """通过 API Key 获取用户

        v5.0.5/P6: 优先按确定性哈希查找（api_key 列已加密存储）；回退到
        明文匹配以兼容尚未迁移的历史行。
        """
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE api_key_hash = ?", (lookup_hash(api_key),))
        row = cursor.fetchone()
        if not row:
            # 兼容历史明文行
            cursor.execute("SELECT * FROM users WHERE api_key = ?", (api_key,))
            row = cursor.fetchone()

        if row:
            return User(
                id=row[0],
                username=row[1],
                email=row[2],
                role=UserRole(row[3]),
                api_key=decrypt_or_none(row[4]),
                created_at=datetime.fromisoformat(row[5]),
                last_login=datetime.fromisoformat(row[6]) if row[6] else None,
                role_template_id=row[8] if len(row) > 8 else None,
            )
        return None

    def get_user_by_email(self, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        
        if row:
            return User(
                id=row[0],
                username=row[1],
                email=row[2],
                role=UserRole(row[3]),
                api_key=decrypt_or_none(row[4]),
                created_at=datetime.fromisoformat(row[5]),
                last_login=datetime.fromisoformat(row[6]) if row[6] else None,
                role_template_id=row[8] if len(row) > 8 else None,
            )
        return None

    def get_all_users(self) -> List[User]:
        """获取所有用户列表"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        
        users = []
        for row in cursor.fetchall():
            users.append(User(
                id=row[0],
                username=row[1],
                email=row[2],
                role=UserRole(row[3]),
                api_key=decrypt_or_none(row[4]),
                created_at=datetime.fromisoformat(row[5]),
                last_login=datetime.fromisoformat(row[6]) if row[6] else None,
                role_template_id=row[8] if len(row) > 8 else None,
            ))
        return users
    
    def update_user(self, user_id: str, **kwargs) -> bool:
        """
        更新用户信息
        
        Args:
            user_id: 用户ID
            **kwargs: 要更新的字段（username, email, role）
        
        Returns:
            bool: 是否更新成功
        """
        conn = self.db._get_conn()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if 'username' in kwargs:
            updates.append("username = ?")
            params.append(kwargs['username'])
        if 'email' in kwargs:
            updates.append("email = ?")
            params.append(kwargs['email'])
        if 'role' in kwargs:
            updates.append("role = ?")
            params.append(kwargs['role'].value)
        if 'role_template_id' in kwargs:
            updates.append("role_template_id = ?")
            params.append(kwargs['role_template_id'])
        if 'password_hash' in kwargs:
            updates.append("password_hash = ?")
            params.append(kwargs['password_hash'])
        if 'api_key' in kwargs:
            updates.append("api_key = ?")
            params.append(kwargs['api_key'])
        if 'api_key_hash' in kwargs:
            updates.append("api_key_hash = ?")
            params.append(kwargs['api_key_hash'])
        
        if not updates:
            return False
        
        params.append(user_id)
        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        
        return cursor.rowcount > 0
    
    def update_last_login(self, user_id: str):
        """更新用户最后登录时间"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now(timezone(timedelta(hours=8))), user_id))
        conn.commit()
    
    def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        
        # 先删除关联数据
        cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM subagent_config WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM subagent_tasks WHERE user_id = ?", (user_id,))
        
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        
        return cursor.rowcount > 0
    
    def link_session_to_user(self, user_id: str, session_id: str):
        """关联用户和会话"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO user_sessions VALUES (?, ?, ?)",
            (user_id, session_id, datetime.now(timezone(timedelta(hours=8))))
        )
        conn.commit()
    
    def get_user_sessions(self, user_id: str) -> List[str]:
        """获取用户的所有会话ID"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT session_id FROM user_sessions WHERE user_id = ?", (user_id,))
        
        return [row[0] for row in cursor.fetchall()]
    
    def get_subagent_config(self, user_id: str, agent_type: str) -> Optional[dict]:
        """获取用户的子代理配置"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM subagent_config WHERE user_id = ? AND agent_type = ?",
            (user_id, agent_type)
        )
        row = cursor.fetchone()
        
        if row:
            return {
                'user_id': row[0],
                'agent_type': row[1],
                'llm_model': row[2],
                'llm_provider': row[3],
                'temperature': row[4],
                'personality_weight': row[5],
                'enabled': bool(row[6])
            }
        return None
    
    def save_subagent_config(self, user_id: str, agent_type: str, config: dict):
        """保存用户的子代理配置"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO subagent_config 
            (user_id, agent_type, llm_model, llm_provider, temperature, personality_weight, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            agent_type,
            config.get('llm_model'),
            config.get('llm_provider'),
            config.get('temperature', 0.7),
            config.get('personality_weight', 0.5),
            int(config.get('enabled', True))
        ))
        conn.commit()
    
    def create_subagent_task(self, user_id: str, session_id: str, agent_type: str, input_data: str) -> str:
        """创建子代理任务"""
        task_id = str(uuid.uuid4())
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO subagent_tasks 
            (task_id, user_id, session_id, agent_type, input, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (task_id, user_id, session_id, agent_type, input_data, 'running', datetime.now(timezone(timedelta(hours=8)))))
        conn.commit()
        return task_id
    
    def update_subagent_task(self, task_id: str, **kwargs):
        """更新子代理任务状态"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if 'output' in kwargs:
            updates.append("output = ?")
            params.append(kwargs['output'])
        if 'status' in kwargs:
            updates.append("status = ?")
            params.append(kwargs['status'])
        if 'completed_at' in kwargs:
            updates.append("completed_at = ?")
            params.append(kwargs['completed_at'])
        
        if not updates:
            return
        
        params.append(task_id)
        cursor.execute(f"UPDATE subagent_tasks SET {', '.join(updates)} WHERE task_id = ?", params)
        conn.commit()
    
    def get_subagent_task(self, task_id: str) -> Optional[dict]:
        """获取子代理任务信息"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subagent_tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        
        if row:
            return {
                'task_id': row[0],
                'user_id': row[1],
                'session_id': row[2],
                'agent_type': row[3],
                'input': row[4],
                'output': row[5],
                'status': row[6],
                'created_at': row[7],
                'completed_at': row[8]
            }
        return None
