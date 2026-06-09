"""Prompt cache — v4.0.0 Phase 2.

Component-level TTL cache for system prompt assembly.
Caches immutable prompt fragments (persona, tool descriptions, skill list)
and rebuilds only the components that change.

多 worker 一致性说明 (v5.0.5/A7)
--------------------------------
本缓存是 **进程内** 的(普通 dict + threading.Lock),不跨进程共享。在
gunicorn/uvicorn 以 ``-w N`` (N>1) 多 worker 运行时,每个 worker 持有
**各自独立** 的 PromptCache 实例:

- 安全性:缓存内容是确定性派生(persona/工具/技能的内容哈希),各 worker
  各自计算得到相同结果,不会串数据。
- 一致性:某 worker 调用 ``invalidate()`` 只清自己的副本;其他 worker 的
  过期由 TTL(默认 300s)兜底。因此改了 persona/技能后,最坏需等一个 TTL
  周期才在所有 worker 生效 —— 这是可接受的最终一致。

若将来需要强一致或即时失效,应换成 Redis 等共享后端;当前进程内实现是有意
为之(零依赖、低延迟),TTL 已限定不一致窗口。
"""
import time
import hashlib
import threading
from typing import Any, Optional, Callable


class PromptCache:
    """TTL cache for prompt fragments with hash-based invalidation.

    Each component is keyed by name + content hash. Recomputes only
    when the content changes, avoiding repeated string assembly.
    """

    def __init__(self, ttl_seconds: int = 300, max_size: int = 50):
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._cache: dict[str, tuple[float, str]] = {}  # key → (expires_at, value)
        self._lock = threading.Lock()

    def get_or_compute(self, key: str, factory: Callable[[], str]) -> str:
        """Return cached value for *key*, or compute + cache it."""
        with self._lock:
            now = time.monotonic()
            if key in self._cache:
                expires_at, value = self._cache[key]
                if now < expires_at:
                    return value

        # Compute outside lock to avoid blocking
        value = factory()
        with self._lock:
            self._cache[key] = (now + self._ttl, value)
            self._evict_if_needed()
        return value

    def invalidate(self, key: str):
        """Force recompute on next access."""
        with self._lock:
            self._cache.pop(key, None)

    def invalidate_prefix(self, prefix: str):
        """Invalidate all keys starting with *prefix*."""
        with self._lock:
            keys = [k for k in self._cache if k.startswith(prefix)]
            for k in keys:
                del self._cache[k]

    def clear(self):
        with self._lock:
            self._cache.clear()

    def stats(self) -> dict:
        with self._lock:
            now = time.monotonic()
            active = sum(1 for exp, _ in self._cache.values() if exp > now)
            expired = len(self._cache) - active
            return {
                "total_entries": len(self._cache),
                "active_entries": active,
                "expired_entries": expired,
                "ttl_seconds": self._ttl,
                "max_size": self._max_size,
            }

    def _evict_if_needed(self):
        if len(self._cache) <= self._max_size:
            return
        # Evict expired first, then oldest by expiry
        now = time.monotonic()
        expired = [k for k, (exp, _) in self._cache.items() if exp <= now]
        for k in expired:
            del self._cache[k]
        if len(self._cache) > self._max_size:
            sorted_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][0])
            for k in sorted_keys[: len(self._cache) - self._max_size]:
                del self._cache[k]


# ── Helpers ─────────────────────────────────────────────────────────


def hash_key(prefix: str, content: str) -> str:
    """Create a stable cache key from prefix + content hash."""
    h = hashlib.sha256(content.encode()).hexdigest()[:16]
    return f"{prefix}:{h}"


# ── Global singleton ────────────────────────────────────────────────

prompt_cache: Optional[PromptCache] = None


def init_prompt_cache(ttl_seconds: int = 300) -> PromptCache:
    global prompt_cache
    prompt_cache = PromptCache(ttl_seconds=ttl_seconds)
    return prompt_cache
