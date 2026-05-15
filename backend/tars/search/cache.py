"""搜索缓存 — 基于 SQLite 的查询结果缓存"""
import hashlib
import json
import time
from typing import List, Dict, Any, Optional


class SearchCache:
    """搜索缓存"""

    def __init__(self, db):
        self.db = db
        self._init_table()

    def _init_table(self):
        """初始化缓存表"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_cache (
                query_hash TEXT PRIMARY KEY,
                query_text TEXT NOT NULL,
                search_type TEXT NOT NULL,
                results_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                ttl_seconds INTEGER NOT NULL DEFAULT 300
            )
        """)
        conn.commit()

    def _make_key(self, query: str, search_type: str, limit: int) -> str:
        """生成缓存 key"""
        raw = f"{query}:{search_type}:{limit}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(
        self,
        query: str,
        search_type: str = "memory",
        limit: int = 5,
    ) -> Optional[List[Dict[str, Any]]]:
        """获取缓存结果"""
        key = self._make_key(query, search_type, limit)
        now = time.time()

        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT results_json, created_at, ttl_seconds FROM search_cache WHERE query_hash = ?",
            (key,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        results_json, created_at, ttl = row
        if now - created_at > ttl:
            # 过期，删除
            cursor.execute("DELETE FROM search_cache WHERE query_hash = ?", (key,))
            conn.commit()
            return None

        try:
            return json.loads(results_json)
        except json.JSONDecodeError:
            return None

    def set(
        self,
        query: str,
        results: List[Dict[str, Any]],
        search_type: str = "memory",
        limit: int = 5,
        ttl_seconds: int = 300,
    ) -> None:
        """设置缓存"""
        key = self._make_key(query, search_type, limit)
        now = time.time()

        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO search_cache (query_hash, query_text, search_type, results_json, created_at, ttl_seconds)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (key, query, search_type, json.dumps(results, ensure_ascii=False, default=str), now, ttl_seconds),
        )
        conn.commit()

    def clear(self, search_type: Optional[str] = None) -> int:
        """清空缓存"""
        conn = self.db._get_conn()
        cursor = conn.cursor()
        if search_type:
            cursor.execute("DELETE FROM search_cache WHERE search_type = ?", (search_type,))
        else:
            cursor.execute("DELETE FROM search_cache")
        conn.commit()
        return cursor.rowcount

    def cleanup_expired(self) -> int:
        """清理过期缓存"""
        now = time.time()
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM search_cache WHERE created_at + ttl_seconds < ?",
            (now,),
        )
        conn.commit()
        return cursor.rowcount
