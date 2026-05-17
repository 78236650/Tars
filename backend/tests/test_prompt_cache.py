"""Tests for TARS prompt cache — Phase 2 Task 6."""
import pytest
import time
from tars.cache.prompt_cache import PromptCache, hash_key


class TestPromptCache:
    """Verify TTL cache behavior: hit, miss, invalidation, eviction."""

    def test_cache_hit(self):
        pc = PromptCache(ttl_seconds=60)
        calls = []

        def factory():
            calls.append(1)
            return "computed_value"

        v1 = pc.get_or_compute("test", factory)
        v2 = pc.get_or_compute("test", factory)
        assert v1 == v2 == "computed_value"
        assert len(calls) == 1  # Only computed once

    def test_cache_expiry(self):
        pc = PromptCache(ttl_seconds=0)
        calls = []

        def factory():
            calls.append(1)
            return f"v{len(calls)}"

        v1 = pc.get_or_compute("exp", factory)
        time.sleep(0.01)
        v2 = pc.get_or_compute("exp", factory)
        assert v1 != v2  # Second call recomputed
        assert len(calls) == 2

    def test_invalidate(self):
        pc = PromptCache(ttl_seconds=3600)
        v1 = pc.get_or_compute("inv", lambda: "old")
        pc.invalidate("inv")
        v2 = pc.get_or_compute("inv", lambda: "new")
        assert v1 == "old"
        assert v2 == "new"

    def test_invalidate_prefix(self):
        pc = PromptCache(ttl_seconds=3600)
        pc.get_or_compute("a:1", lambda: "a1")
        pc.get_or_compute("a:2", lambda: "a2")
        pc.get_or_compute("b:1", lambda: "b1")
        pc.invalidate_prefix("a:")
        # "a:" keys should recompute; "b:" stays
        assert pc.get_or_compute("a:1", lambda: "a1-new") == "a1-new"
        assert pc.get_or_compute("b:1", lambda: "b1-new") == "b1"

    def test_clear(self):
        pc = PromptCache(ttl_seconds=3600)
        pc.get_or_compute("x", lambda: "x")
        pc.get_or_compute("y", lambda: "y")
        assert pc.stats()["total_entries"] == 2
        pc.clear()
        assert pc.stats()["total_entries"] == 0

    def test_hash_key_stability(self):
        k1 = hash_key("p", "hello world")
        k2 = hash_key("p", "hello world")
        k3 = hash_key("p", "different")
        assert k1 == k2
        assert k1 != k3
        assert k1.startswith("p:")

    def test_eviction_on_max_size(self):
        pc = PromptCache(ttl_seconds=3600, max_size=3)
        for i in range(5):
            pc.get_or_compute(f"k{i}", lambda i=i: f"v{i}")
        stats = pc.stats()
        assert stats["total_entries"] <= 3


class TestPromptCacheConcurrency:
    """Verify thread-safe access."""

    def test_concurrent_access(self):
        import threading
        pc = PromptCache(ttl_seconds=3600, max_size=50)
        errors = []

        def worker(i):
            try:
                pc.get_or_compute(f"k{i % 10}", lambda: f"v{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert pc.stats()["total_entries"] <= 10
