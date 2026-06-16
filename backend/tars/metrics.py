"""Prometheus metrics (TARS v5.0.5 / P3).

Defines process-wide metric objects and a middleware that records HTTP request
counts and latency. Tool-execution timing is recorded from the dispatcher.

Import is guarded: if ``prometheus_client`` is unavailable the module exposes
no-op stand-ins so the app still starts (metrics simply aren't collected).
"""

from __future__ import annotations

import time

try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

    _ENABLED = True
except Exception:  # pragma: no cover - prometheus optional
    _ENABLED = False
    CONTENT_TYPE_LATEST = "text/plain"


if _ENABLED:
    HTTP_REQUESTS = Counter(
        "tars_http_requests_total",
        "HTTP requests",
        ["method", "path", "status"],
    )
    HTTP_LATENCY = Histogram(
        "tars_http_request_duration_seconds",
        "HTTP request latency",
        ["method", "path"],
    )
    TOOL_EXECUTIONS = Counter(
        "tars_tool_executions_total",
        "Tool executions",
        ["tool", "outcome"],
    )
    TOOL_LATENCY = Histogram(
        "tars_tool_duration_seconds",
        "Tool execution latency",
        ["tool"],
    )
    LLM_REQUESTS = Counter(
        "tars_llm_requests_total",
        "LLM requests",
        ["model", "provider"],
    )
    LLM_TOKENS = Counter(
        "tars_llm_tokens_total",
        "LLM tokens",
        ["model", "provider", "type"],
    )
    LLM_LATENCY = Histogram(
        "tars_llm_duration_seconds",
        "LLM request latency",
        ["model", "provider"],
    )


def metrics_enabled() -> bool:
    return _ENABLED


def render_latest() -> bytes:
    if not _ENABLED:
        return b"# prometheus_client unavailable\n"
    return generate_latest()

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def _route_template(request: Request) -> str:
    """Use the matched route path (``/api/users/{id}``) not the raw URL, so
    per-id paths don't explode metric cardinality. Falls back to the raw path."""
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request count + latency per (method, route)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not _ENABLED:
            return await call_next(request)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            path = _route_template(request)
            elapsed = time.perf_counter() - start
            try:
                HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
                HTTP_LATENCY.labels(request.method, path).observe(elapsed)
            except Exception:
                pass



def record_tool_execution(tool: str, success: bool, elapsed_seconds: float) -> None:
    """Called from the dispatcher after each tool run."""
    if not _ENABLED:
        return
    try:
        TOOL_EXECUTIONS.labels(tool, "success" if success else "failed").inc()
        TOOL_LATENCY.labels(tool).observe(elapsed_seconds)
    except Exception:
        pass


def record_llm_call(
    model: str,
    provider: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_s: float = 0.0,
) -> None:
    """Called after each LLM request. Records counters and latency histogram."""
    if not _ENABLED:
        return
    try:
        safe_model = (model or "unknown").replace('"', '_')
        safe_provider = (provider or "unknown").replace('"', '_')
        LLM_REQUESTS.labels(safe_model, safe_provider).inc()
        if prompt_tokens > 0:
            LLM_TOKENS.labels(safe_model, safe_provider, "prompt").inc(prompt_tokens)
        if completion_tokens > 0:
            LLM_TOKENS.labels(safe_model, safe_provider, "completion").inc(completion_tokens)
        if latency_s > 0:
            LLM_LATENCY.labels(safe_model, safe_provider).observe(latency_s)
    except Exception:
        pass
