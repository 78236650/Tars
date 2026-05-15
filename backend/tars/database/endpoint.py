import uuid
import json
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from .base import Database


@dataclass
class Endpoint:
    id: str
    name: str
    base_url: str
    api_key: Optional[str] = None
    models: List[str] = field(default_factory=list)
    enabled: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class EndpointStore:
    def __init__(self, db: Database):
        self.db = db

    def get_all(self) -> List[Endpoint]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, base_url, api_key, models, enabled, created_at, updated_at
            FROM endpoints
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        return [self._row_to_endpoint(row) for row in rows]

    def get_enabled(self) -> List[Endpoint]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, base_url, api_key, models, enabled, created_at, updated_at
            FROM endpoints
            WHERE enabled = 1
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        return [self._row_to_endpoint(row) for row in rows]

    def get_by_id(self, endpoint_id: str) -> Optional[Endpoint]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, base_url, api_key, models, enabled, created_at, updated_at
            FROM endpoints WHERE id = ?
        """, (endpoint_id,))
        row = cursor.fetchone()
        return self._row_to_endpoint(row) if row else None

    def create(self, name: str, base_url: str, api_key: Optional[str] = None,
               models: Optional[List[str]] = None) -> Endpoint:
        endpoint_id = str(uuid.uuid4())
        now = datetime.now(timezone(timedelta(hours=8))).isoformat()
        models_json = json.dumps(models or [], ensure_ascii=False)

        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO endpoints (id, name, base_url, api_key, models, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """, (endpoint_id, name, base_url, api_key, models_json, now, now))
        conn.commit()

        return Endpoint(
            id=endpoint_id, name=name, base_url=base_url,
            api_key=api_key, models=models or [], enabled=True,
            created_at=now, updated_at=now
        )

    def update(self, endpoint_id: str, **kwargs) -> Optional[Endpoint]:
        now = datetime.now(timezone(timedelta(hours=8))).isoformat()
        updates = []
        params = []

        allowed_fields = ["name", "base_url", "api_key", "models", "enabled"]
        for field in allowed_fields:
            if field in kwargs:
                value = kwargs[field]
                if field == "models":
                    value = json.dumps(value, ensure_ascii=False)
                elif field == "enabled":
                    value = 1 if value else 0
                updates.append(f"{field} = ?")
                params.append(value)

        if not updates:
            return self.get_by_id(endpoint_id)

        params.extend([now, endpoint_id])
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE endpoints SET {', '.join(updates)}, updated_at = ?
            WHERE id = ?
        """, params)
        conn.commit()

        return self.get_by_id(endpoint_id)

    def delete(self, endpoint_id: str) -> bool:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM endpoints WHERE id = ?", (endpoint_id,))
        conn.commit()
        return cursor.rowcount > 0

    def _row_to_endpoint(self, row) -> Optional[Endpoint]:
        if not row:
            return None
        models = []
        if row[4]:
            try:
                models = json.loads(row[4])
            except (json.JSONDecodeError, TypeError):
                models = []
        return Endpoint(
            id=row[0], name=row[1], base_url=row[2],
            api_key=row[3], models=models, enabled=bool(row[5]),
            created_at=row[6], updated_at=row[7]
        )