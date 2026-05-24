"""Unified evolution feedback ingestion."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..database.base import Database, get_local_now
from .models import EvolutionEvent


class FeedbackCollector:
    def __init__(self, db: Database):
        self.db = db

    def record(self, event: EvolutionEvent) -> str:
        event_id = event.id or str(uuid.uuid4())
        created = event.created_at or get_local_now()
        if isinstance(created, datetime):
            created_at = created.isoformat()
        else:
            created_at = str(created)
        self.db.insert_evolution_event(
            event_id=event_id,
            tenant_id=event.tenant_id,
            user_id=event.user_id,
            source=event.source,
            signal=event.signal,
            payload_json=json.dumps(event.payload, ensure_ascii=False),
            weight=event.weight,
            created_at=created_at,
        )
        return event_id

    def count_recent(self, tenant_id: str = "default", days: int = 7) -> int:
        return self.db.count_evolution_events(tenant_id=tenant_id, days=days)

    def record_insight_feedback(
        self,
        tenant_id: str,
        user_id: str,
        question_log_id: str,
        feedback: int,
        *,
        metric_key: Optional[str] = None,
    ) -> Optional[str]:
        if feedback >= 0:
            return None
        return self.record(
            EvolutionEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                source="insight",
                signal="metric_downvote",
                payload={"question_log_id": question_log_id, "metric_key": metric_key},
                weight=2.0,
            )
        )

    def record_explicit_feedback(
        self,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        feedback: str,
    ) -> str:
        signal = "thumbs_up" if feedback in ("up", "positive", "1") else "thumbs_down"
        weight = 1.0 if signal == "thumbs_up" else 2.0
        return self.record(
            EvolutionEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                source="explicit",
                signal=signal,
                payload={"conversation_id": conversation_id},
                weight=weight,
            )
        )

    def record_tool_result(
        self,
        tenant_id: str,
        user_id: str,
        tool: str,
        success: bool,
        *,
        session_id: Optional[str] = None,
    ) -> str:
        return self.record(
            EvolutionEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                source="implicit",
                signal="tool_ok" if success else "tool_fail",
                payload={"tool": tool, "session_id": session_id},
                weight=1.0,
            )
        )
