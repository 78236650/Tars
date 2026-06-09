"""Agent decision tracing (v5.0.5/A6).

Records the agent's internal decisions — skill routing, memory retrieval,
knowledge promotion — into the ``agent_decisions`` table, tagged with the
request-scoped ``trace_id`` so a full decision chain can be replayed by trace.

Recording is best-effort and must never break the agent loop: every write is
guarded and failures are swallowed (logged at debug). The table is created by
migration v2 (see ``database/migrations.py``).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("tars.decisions")

# Known decision types (free-form TEXT in DB; these are the canonical values).
SKILL_ROUTE = "skill_route"
MEMORY_RETRIEVE = "memory_retrieve"
KB_PROMOTE = "kb_promote"


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def record_decision(
    db,
    *,
    decision_type: str,
    session_id: str = "",
    tenant_id: str = "default",
    user_id: str = "default",
    decision_input: Any = None,
    decision_output: Any = None,
    reasoning: str = "",
) -> Optional[str]:
    """Record one decision. Returns the row id, or None on failure.

    ``decision_input`` / ``decision_output`` are JSON-serialized if not already
    strings. ``trace_id`` is pulled from the current request context.
    """
    try:
        from ..context import get_current_trace_id

        trace_id = get_current_trace_id()
    except Exception:
        trace_id = None

    def _ser(v: Any) -> Optional[str]:
        if v is None or isinstance(v, str):
            return v
        try:
            return json.dumps(v, ensure_ascii=False, default=str)[:4000]
        except Exception:
            return str(v)[:4000]

    try:
        decision_id = str(uuid.uuid4())
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agent_decisions
            (id, session_id, tenant_id, user_id, trace_id, decision_type,
             decision_input, decision_output, reasoning, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                session_id or "",
                tenant_id or "default",
                user_id or "default",
                trace_id,
                decision_type,
                _ser(decision_input),
                _ser(decision_output),
                (reasoning or "")[:2000],
                _now(),
            ),
        )
        conn.commit()
        return decision_id
    except Exception as exc:
        logger.debug("record_decision failed: %s", exc)
        return None


def query_decisions(
    db,
    *,
    trace_id: str = "",
    session_id: str = "",
    decision_type: str = "",
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Query decisions by trace_id / session_id / type. Returns dict rows."""
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        conditions: List[str] = []
        params: List[Any] = []
        if trace_id:
            conditions.append("trace_id = ?")
            params.append(trace_id)
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if decision_type:
            conditions.append("decision_type = ?")
            params.append(decision_type)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(int(limit))
        cursor.execute(
            f"""
            SELECT id, session_id, tenant_id, user_id, trace_id, decision_type,
                   decision_input, decision_output, reasoning, created_at
            FROM agent_decisions{where}
            ORDER BY created_at ASC
            LIMIT ?
            """,
            tuple(params),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": r[0],
                "session_id": r[1],
                "tenant_id": r[2],
                "user_id": r[3],
                "trace_id": r[4],
                "decision_type": r[5],
                "decision_input": r[6],
                "decision_output": r[7],
                "reasoning": r[8],
                "created_at": str(r[9]),
            }
            for r in rows
        ]
    except Exception as exc:
        logger.debug("query_decisions failed: %s", exc)
        return []
