# TARS Database - Custom Model Store
# 自定义模型配置存储

import uuid
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from .base import Database


@dataclass
class CustomModel:
    id: str
    name: str
    base_url: str
    model: str
    api_key: Optional[str] = None
    description: Optional[str] = None
    is_enabled: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CustomModelStore:
    def __init__(self, db: Database):
        self.db = db

    def get_all(self) -> List[CustomModel]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, base_url, model, api_key, description, is_enabled, created_at, updated_at
            FROM custom_models
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        return [
            CustomModel(
                id=row[0],
                name=row[1],
                base_url=row[2],
                model=row[3],
                api_key=row[4],
                description=row[5],
                is_enabled=bool(row[6]),
                created_at=row[7],
                updated_at=row[8]
            )
            for row in rows
        ]

    def get_enabled(self) -> List[CustomModel]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, base_url, model, api_key, description, is_enabled, created_at, updated_at
            FROM custom_models
            WHERE is_enabled = 1
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        return [
            CustomModel(
                id=row[0],
                name=row[1],
                base_url=row[2],
                model=row[3],
                api_key=row[4],
                description=row[5],
                is_enabled=bool(row[6]),
                created_at=row[7],
                updated_at=row[8]
            )
            for row in rows
        ]

    def get_by_id(self, model_id: str) -> Optional[CustomModel]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, base_url, model, api_key, description, is_enabled, created_at, updated_at
            FROM custom_models WHERE id = ?
        """, (model_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return CustomModel(
            id=row[0],
            name=row[1],
            base_url=row[2],
            model=row[3],
            api_key=row[4],
            description=row[5],
            is_enabled=bool(row[6]),
            created_at=row[7],
            updated_at=row[8]
        )

    def create(self, name: str, base_url: str, model: str, api_key: Optional[str] = None,
               description: Optional[str] = None) -> CustomModel:
        model_id = str(uuid.uuid4())
        now = datetime.now(timezone(timedelta(hours=8))).isoformat()

        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO custom_models (id, name, base_url, model, api_key, description, is_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (model_id, name, base_url, model, api_key, description, now, now))
        conn.commit()

        return CustomModel(
            id=model_id,
            name=name,
            base_url=base_url,
            model=model,
            api_key=api_key,
            description=description,
            is_enabled=True,
            created_at=now,
            updated_at=now
        )

    def update(self, model_id: str, **kwargs) -> Optional[CustomModel]:
        now = datetime.now(timezone(timedelta(hours=8))).isoformat()
        updates = []
        params = []

        allowed_fields = ["name", "base_url", "model", "api_key", "description", "is_enabled"]
        for field in allowed_fields:
            if field in kwargs:
                value = kwargs[field]
                if field == "is_enabled":
                    value = 1 if value else 0
                updates.append(f"{field} = ?")
                params.append(value)

        if not updates:
            return self.get_by_id(model_id)

        params.extend([now, model_id])
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE custom_models SET {', '.join(updates)}, updated_at = ?
            WHERE id = ?
        """, params)
        conn.commit()

        return self.get_by_id(model_id)

    def delete(self, model_id: str) -> bool:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM custom_models WHERE id = ?", (model_id,))
        conn.commit()
        return cursor.rowcount > 0

    def toggle_enabled(self, model_id: str, enabled: bool) -> Optional[CustomModel]:
        return self.update(model_id, is_enabled=enabled)
