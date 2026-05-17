"""LLM connection pool — v4.0.0 Phase 2.

Provides a shared httpx.AsyncClient with connection reuse
and configurable pool limits, replacing per-request clients.
"""
import os
import httpx
from typing import Optional


class ConnectionPool:
    """Manages one shared httpx.AsyncClient for all LLM providers.

    Uses httpx's built-in connection pooling (keep-alive, max_connections).
    """

    def __init__(
        self,
        max_connections: int = 20,
        max_keepalive: int = 10,
        connect_timeout: float = 30.0,
        read_timeout: float = 600.0,
    ):
        read_s = float(os.getenv("TARS_LLM_READ_TIMEOUT", str(read_timeout)))
        connect_s = float(os.getenv("TARS_LLM_CONNECT_TIMEOUT", str(connect_timeout)))

        limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive,
        )

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=connect_s,
                read=read_s,
                write=120.0,
                pool=30.0,
            ),
            limits=limits,
        )

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client

    async def close(self):
        await self._client.aclose()

    def stats(self) -> dict:
        """Return pool statistics."""
        try:
            pool = self._client._transport._pool
            return {
                "max_connections": pool._max_connections,
                "max_keepalive": pool._max_keepalive_connections,
                "num_connections": len(pool.connections),
            }
        except Exception:
            return {"max_connections": "n/a", "max_keepalive": "n/a"}


# ── Global singleton ────────────────────────────────────────────────

_pool: Optional[ConnectionPool] = None


def get_connection_pool(
    max_connections: int = 20,
    max_keepalive: int = 10,
) -> ConnectionPool:
    """Get or create the shared connection pool."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            max_connections=max_connections,
            max_keepalive=max_keepalive,
        )
    return _pool


async def close_connection_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
