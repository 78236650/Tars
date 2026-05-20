"""In-process SSE event buffer for InsightForge forge runs (INS-2.0)."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from typing import Any, AsyncIterator, Deque, Dict, Iterator, List, Optional

_MAX_EVENTS_PER_RUN = 100
_MAX_CONNECTIONS = 50

_lock = threading.Lock()
_connections = 0
_buffers: Dict[str, Deque[dict]] = {}
_seq: Dict[str, int] = {}


def _next_id(run_id: str) -> int:
    _seq[run_id] = _seq.get(run_id, 0) + 1
    return _seq[run_id]


def publish(run_id: str, event_type: str, data: Optional[Dict[str, Any]] = None) -> int:
    with _lock:
        buf = _buffers.setdefault(run_id, deque(maxlen=_MAX_EVENTS_PER_RUN))
        event_id = _next_id(run_id)
        buf.append(
            {
                "id": event_id,
                "event": event_type,
                "data": data or {},
                "ts": time.time(),
            }
        )
        return event_id


def list_events(run_id: str, after_id: int = 0) -> List[dict]:
    with _lock:
        buf = _buffers.get(run_id, deque())
        return [e for e in buf if e["id"] > after_id]


def acquire_connection() -> bool:
    global _connections
    with _lock:
        if _connections >= _MAX_CONNECTIONS:
            return False
        _connections += 1
        return True


def release_connection() -> None:
    global _connections
    with _lock:
        _connections = max(0, _connections - 1)


def _format_sse_event(ev: dict) -> str:
    payload = ev.get("data") or {}
    return (
        f"id: {ev['id']}\n"
        f"event: {ev['event']}\n"
        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    )


def iter_sse(
    run_id: str,
    last_event_id: int = 0,
    *,
    heartbeat_sec: int = 30,
) -> Iterator[str]:
    """Sync SSE iterator (tests only). Prefer ``aiter_sse`` in production."""
    cursor = last_event_id
    last_heartbeat = time.time()
    try:
        while True:
            events = list_events(run_id, cursor)
            for ev in events:
                cursor = ev["id"]
                yield _format_sse_event(ev)
            now = time.time()
            if now - last_heartbeat >= heartbeat_sec:
                last_heartbeat = now
                yield ": heartbeat\n\n"
            time.sleep(0.5)
    finally:
        release_connection()


async def aiter_sse(
    run_id: str,
    last_event_id: int = 0,
    *,
    heartbeat_sec: int = 30,
    poll_interval_sec: float = 0.5,
) -> AsyncIterator[str]:
    """Async SSE stream — must not block the event loop (P0 #2)."""
    cursor = last_event_id
    last_heartbeat = time.time()
    try:
        while True:
            events = list_events(run_id, cursor)
            for ev in events:
                cursor = ev["id"]
                yield _format_sse_event(ev)
            now = time.time()
            if now - last_heartbeat >= heartbeat_sec:
                last_heartbeat = now
                yield ": heartbeat\n\n"
            await asyncio.sleep(poll_interval_sec)
    finally:
        release_connection()
