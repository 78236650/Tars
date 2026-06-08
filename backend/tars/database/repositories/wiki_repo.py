# TARS Wiki Repository
# wiki_pages 元数据表的读写 —— 维护 wiki 页与源记忆的双向链接。

import json
from typing import Any, Dict, List, Optional

from tars.database.connection import ConnectionManager
from tars.database.models import get_local_now
from tars.database.sql_dialect import placeholder
from tars.org import ORG_ID


class WikiRepo:
    """Wiki 页元数据 Repository。正文仍存于文件系统，本表只存关联关系。"""

    def __init__(self, cm: ConnectionManager):
        self._cm = cm

    def _get_conn(self):
        return self._cm.get_conn()

    @property
    def _ph(self) -> str:
        return placeholder(self._cm.dialect)

    def upsert_wiki_page(
        self,
        page_name: str,
        *,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        source_memory_ids: Optional[List[str]] = None,
        source_type: str = "manual",
        tenant_id: str = ORG_ID,
    ) -> None:
        """插入或更新一条 wiki 页元数据。"""
        now = get_local_now().isoformat()
        if source_memory_ids is not None and not isinstance(source_memory_ids, list):
            raise TypeError(
                f"source_memory_ids must be a list or None, got {type(source_memory_ids).__name__}"
            )
        ids_json = json.dumps(source_memory_ids or [], ensure_ascii=False)
        ph = self._ph
        conn = self._get_conn()
        cursor = conn.cursor()
        # 复合主键 (tenant_id, page_name)：冲突子句须含两列，避免跨租户同名页互相覆盖。
        excluded = "EXCLUDED" if self._cm.dialect == "postgres" else "excluded"
        sql = (
            f"INSERT INTO wiki_pages "
            f"(page_name, tenant_id, title, summary, source_memory_ids, source_type, created_at, updated_at) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}) "
            f"ON CONFLICT (tenant_id, page_name) DO UPDATE SET "
            f"title = {excluded}.title, summary = {excluded}.summary, "
            f"source_memory_ids = {excluded}.source_memory_ids, "
            f"source_type = {excluded}.source_type, updated_at = {excluded}.updated_at"
        )
        cursor.execute(
            sql,
            (page_name, tenant_id, title, summary, ids_json, source_type, now, now),
        )
        conn.commit()

    def get_wiki_page_meta(
        self, page_name: str, *, tenant_id: str = ORG_ID
    ) -> Optional[Dict[str, Any]]:
        """读取单页元数据；返回 dict（source_memory_ids 已解析为 list）。"""
        ph = self._ph
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT page_name, tenant_id, title, summary, source_memory_ids, "
            f"source_type, created_at, updated_at FROM wiki_pages "
            f"WHERE page_name = {ph} AND tenant_id = {ph}",
            (page_name, tenant_id),
        )
        row = cursor.fetchone()
        return self._row_to_meta(row) if row else None

    def find_pages_by_memory_id(
        self, memory_id: str, *, tenant_id: str = ORG_ID
    ) -> List[Dict[str, Any]]:
        """反向查询：给一条记忆，找出它升格进了哪些 wiki 页。"""
        if not memory_id:
            return []
        ph = self._ph
        conn = self._get_conn()
        cursor = conn.cursor()
        # source_memory_ids 是 JSON 数组文本，用 LIKE 包含匹配（两方言通用）。
        like = f'%"{memory_id}"%'
        cursor.execute(
            f"SELECT page_name, tenant_id, title, summary, source_memory_ids, "
            f"source_type, created_at, updated_at FROM wiki_pages "
            f"WHERE tenant_id = {ph} AND source_memory_ids LIKE {ph}",
            (tenant_id, like),
        )
        rows = cursor.fetchall() or []
        out: List[Dict[str, Any]] = []
        for row in rows:
            meta = self._row_to_meta(row)
            # LIKE 可能误匹配子串，二次校验解析后的列表确含该 id。
            if memory_id in meta.get("source_memory_ids", []):
                out.append(meta)
        return out

    @staticmethod
    def _row_to_meta(row) -> Dict[str, Any]:
        try:
            ids = json.loads(row[4]) if row[4] else []
        except (ValueError, TypeError):
            ids = []
        return {
            "page_name": row[0],
            "tenant_id": row[1],
            "title": row[2],
            "summary": row[3],
            "source_memory_ids": ids,
            "source_type": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }
