"""Per-tenant InsightForge LLM preferences."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..database.base import Database, get_local_now


@dataclass
class InsightLlmSettings:
    tenant_id: str
    use_chat_default: bool = True
    provider: str = "ollama"
    model: str = ""
    endpoint_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "use_chat_default": self.use_chat_default,
            "provider": self.provider,
            "model": self.model,
            "endpoint_id": self.endpoint_id,
        }

    @classmethod
    def from_dict(cls, tenant_id: str, data: Optional[Dict[str, Any]]) -> "InsightLlmSettings":
        if not data:
            return cls(tenant_id=tenant_id)
        return cls(
            tenant_id=tenant_id,
            use_chat_default=bool(data.get("use_chat_default", True)),
            provider=str(data.get("provider") or "ollama"),
            model=str(data.get("model") or ""),
            endpoint_id=data.get("endpoint_id"),
        )


class InsightLlmSettingsStore:
    def __init__(self, db: Database):
        self.db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insight_llm_settings (
                tenant_id TEXT PRIMARY KEY,
                use_chat_default INTEGER NOT NULL DEFAULT 1,
                provider TEXT NOT NULL DEFAULT 'ollama',
                model TEXT NOT NULL DEFAULT '',
                endpoint_id TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()

    def get(self, tenant_id: str) -> InsightLlmSettings:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT use_chat_default, provider, model, endpoint_id
            FROM insight_llm_settings WHERE tenant_id = ?
            """,
            (tenant_id,),
        )
        row = cursor.fetchone()
        if not row:
            return InsightLlmSettings(tenant_id=tenant_id)
        return InsightLlmSettings(
            tenant_id=tenant_id,
            use_chat_default=bool(row[0]),
            provider=row[1] or "ollama",
            model=row[2] or "",
            endpoint_id=row[3],
        )

    def save(self, settings: InsightLlmSettings) -> InsightLlmSettings:
        now = get_local_now().isoformat()
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO insight_llm_settings (
                tenant_id, use_chat_default, provider, model, endpoint_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id) DO UPDATE SET
                use_chat_default = excluded.use_chat_default,
                provider = excluded.provider,
                model = excluded.model,
                endpoint_id = excluded.endpoint_id,
                updated_at = excluded.updated_at
            """,
            (
                settings.tenant_id,
                1 if settings.use_chat_default else 0,
                settings.provider,
                settings.model,
                settings.endpoint_id,
                now,
            ),
        )
        conn.commit()
        return settings
