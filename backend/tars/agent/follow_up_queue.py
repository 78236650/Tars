"""Lightweight follow-up queue while an agent turn is running."""
from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional


@dataclass(frozen=True)
class FollowUpItem:
    raw_message: str
    session_id: str
    content: str
    file_ids: list | None = None

    @classmethod
    def from_raw(cls, raw_message: str, data: dict) -> "FollowUpItem":
        file_ids = data.get("file_ids")
        return cls(
            raw_message=raw_message,
            session_id=data.get("session_id", "default"),
            content=data.get("content", ""),
            file_ids=file_ids if file_ids else None,
        )


class FollowUpQueue:
    """Per-session FIFO queue for user messages received during an active turn."""

    def __init__(self) -> None:
        self._pending: Dict[str, Deque[FollowUpItem]] = defaultdict(deque)
        self._busy_sessions: set[str] = set()
        self._cancel_events: Dict[str, asyncio.Event] = {}

    def is_busy(self, session_id: str) -> bool:
        return session_id in self._busy_sessions

    def try_acquire(self, session_id: str) -> bool:
        """Claim the session turn slot without awaiting (asyncio-safe)."""
        if session_id in self._busy_sessions:
            return False
        self._busy_sessions.add(session_id)
        return True

    def mark_busy(self, session_id: str) -> None:
        self._busy_sessions.add(session_id)

    def mark_idle(self, session_id: str) -> None:
        self._busy_sessions.discard(session_id)

    def enqueue(self, item: FollowUpItem) -> int:
        self._pending[item.session_id].append(item)
        return len(self._pending[item.session_id])

    def pop(self, session_id: str) -> Optional[FollowUpItem]:
        queue = self._pending.get(session_id)
        if not queue:
            return None
        return queue.popleft()

    def pending(self, session_id: str) -> int:
        return len(self._pending.get(session_id, ()))

    def _cancel_event(self, session_id: str) -> asyncio.Event:
        if session_id not in self._cancel_events:
            self._cancel_events[session_id] = asyncio.Event()
        return self._cancel_events[session_id]

    def reset_cancel(self, session_id: str) -> None:
        self._cancel_event(session_id).clear()

    def request_cancel(self, session_id: str) -> None:
        self._cancel_event(session_id).set()

    def is_cancelled(self, session_id: str) -> bool:
        return self._cancel_event(session_id).is_set()

    def clear_pending(self, session_id: str) -> int:
        queue = self._pending.get(session_id)
        if not queue:
            return 0
        count = len(queue)
        queue.clear()
        return count
