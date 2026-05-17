"""Tests for TARS connection pool — Phase 2 Task 4."""
import pytest
from tars.models.connection_pool import ConnectionPool, get_connection_pool


class TestConnectionPool:
    """Verify shared connection pool creation and reuse."""

    def test_create_pool(self):
        pool = ConnectionPool(max_connections=10, max_keepalive=5)
        assert pool.client is not None
        s = pool.stats()
        assert "max_connections" in s
        assert "max_keepalive" in s

    def test_singleton_returns_same_pool(self):
        p1 = get_connection_pool(max_connections=5)
        p2 = get_connection_pool()
        assert p1 is p2  # Same instance

    def test_pool_reuse(self):
        pool = ConnectionPool(max_keepalive=10)
        assert pool.client is not None
        # Pool should be usable for multiple requests
        assert pool.stats() is not None

    @pytest.mark.asyncio
    async def test_async_close(self):
        pool = ConnectionPool()
        await pool.close()
        # After close, should be able to create a new one
        pool2 = ConnectionPool()
        assert pool2 is not pool
        await pool2.close()

    def test_env_timeout_override(self, monkeypatch):
        monkeypatch.setenv("TARS_LLM_READ_TIMEOUT", "120")
        monkeypatch.setenv("TARS_LLM_CONNECT_TIMEOUT", "10")
        pool = ConnectionPool()
        timeout = pool.client.timeout
        assert timeout.read == 120.0
        assert timeout.connect == 10.0
