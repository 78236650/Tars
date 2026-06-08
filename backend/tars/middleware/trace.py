"""Assign a trace id to every request (TARS v5.0.5 / P2).

Reads an inbound ``X-Trace-ID`` header when present (so an upstream proxy or
client can propagate its own id), otherwise generates one. The id is stored in
a contextvar (picked up by the logging Formatter and audit log) and echoed back
in the response header for client-side correlation.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..context import current_trace_id

_HEADER = "X-Trace-ID"
_MAX_LEN = 128


def _inbound_trace_id(request: Request) -> str:
    raw = request.headers.get(_HEADER, "").strip()
    if raw:
        # Bound length and strip anything log-injection-y.
        cleaned = "".join(c for c in raw[:_MAX_LEN] if c.isalnum() or c in "-_.")
        if cleaned:
            return cleaned
    return uuid.uuid4().hex


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Populate the trace_id contextvar for the duration of each request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = _inbound_trace_id(request)
        token = current_trace_id.set(trace_id)
        try:
            response = await call_next(request)
            response.headers[_HEADER] = trace_id
            return response
        finally:
            current_trace_id.reset(token)
