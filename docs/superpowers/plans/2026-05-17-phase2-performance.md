---
doc_type: plan
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# Phase 2: Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize TARS for multi-user concurrent access — faster startup, connection reuse, prompt caching, and fair rate limiting.

**Architecture:** New modules `backend/tars/cache/`, `backend/tars/concurrency/`, and `backend/tars/models/connection_pool.py` provide performance services. Each is independent and integrates at specific points (startup, LLM call, system prompt assembly).

**Tech Stack:** Python 3.8+, asyncio, httpx connection pooling, in-memory TTL cache

**Dependencies:** None (can run in parallel with Phase 1)

---

## File Structure

```
backend/tars/
├── lazy.py                      # 延迟导入工具
├── cache/
│   ├── __init__.py
│   └── prompt_cache.py          # System Prompt 组件级缓存
├── concurrency/
│   ├── __init__.py
│   └── limiter.py               # LLM 并发限流 + 公平调度
└── models/
    └── connection_pool.py       # httpx 连接复用池

config/
└── concurrency.yaml             # 并发配置

backend/tests/
├── test_prompt_cache.py
├── test_limiter.py
└── test_connection_pool.py
```

---

## Task 1: Lazy Import — 延迟导入工具

**Files:**
- Create: `backend/tars/lazy.py`

- [ ] **Step 1: Implement lazy import utility**

```python
# backend/tars/lazy.py
import importlib
from typing import Any

class LazyModule:
    """Delays import until first attribute access."""
    def __init__(self, module_path: str):
        self._module_path = module_path
        self._module = None

    def _load(self):
        if self._module is None:
            self._module = importlib.import_module(self._module_path)
        return self._module

    def __getattr__(self, name: str) -> Any:
        return getattr(self._load(), name)

def lazy_import(module_path: str) -> LazyModule:
    return LazyModule(module_path)
```

- [ ] **Step 2: Verify it works**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -c "from tars.lazy import lazy_import; m = lazy_import('json'); print(m.dumps({'ok': True}))"`
Expected: `{"ok": true}`

- [ ] **Step 3: Commit**

```bash
git add backend/tars/lazy.py
git commit -m "feat(perf): add lazy import utility for deferred module loading"
```

---

## Task 2: Startup Optimization — 启动流程重排

**Files:**
- Modify: `backend/tars/main.py`
- Modify: `backend/tars/memory/embeddings.py`

- [ ] **Step 1: Apply lazy imports to heavy dependencies in main.py**

Replace top-level imports of heavy modules with lazy loading. In `backend/tars/main.py`:

```python
# Replace direct heavy imports with conditional/deferred loading
# Move these OUT of top-level:
# - MemoryScheduler (only needed after startup)
# - EvolutionManager (rarely used)
# - MeetingRecognizerTool (optional module)

# Keep at top level (fast, always needed):
# - FastAPI, Database, AgentV2, ConnectionManager, PermissionManager
```

- [ ] **Step 2: Make embedding model load lazily**

In `backend/tars/memory/embeddings.py`, wrap model loading:

```python
# Change from:
#   self.model = SentenceTransformer(model_name)
# To:
class EmbeddingProvider:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def encode(self, texts, **kwargs):
        return self.model.encode(texts, **kwargs)
```

- [ ] **Step 3: Measure startup time improvement**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && time python -c "from tars.main import app; print('loaded')"`
Expected: Faster than before (baseline first, then compare)

- [ ] **Step 4: Commit**

```bash
git add backend/tars/main.py backend/tars/memory/embeddings.py
git commit -m "feat(perf): defer heavy imports for faster startup"
```

---

## Task 3: Skills Manifest Cache — 技能扫描缓存

**Files:**
- Modify: `backend/tars/skills/loader.py`

- [ ] **Step 1: Add manifest caching to skill loader**

```python
# In backend/tars/skills/loader.py, add caching logic:

import json
import os
from pathlib import Path

CACHE_PATH = Path.home() / ".tars" / "cache" / "skills_manifest.json"

class SkillLoader:
    def load_all(self, skills_dir: str, use_cache: bool = True):
        if use_cache:
            cached = self._load_cache(skills_dir)
            if cached is not None:
                return cached

        # Original scan logic
        skills = self._scan_directory(skills_dir)

        # Save cache
        self._save_cache(skills_dir, skills)
        return skills

    def _load_cache(self, skills_dir: str):
        if not CACHE_PATH.exists():
            return None
        try:
            with open(CACHE_PATH) as f:
                cache = json.load(f)
            # Validate: check if any file mtime is newer than cache
            cache_time = cache.get("timestamp", 0)
            for path in Path(skills_dir).rglob("*"):
                if path.stat().st_mtime > cache_time:
                    return None  # Cache stale
            return cache.get("skills", [])
        except Exception:
            return None

    def _save_cache(self, skills_dir: str, skills):
        import time
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            json.dump({"timestamp": time.time(), "skills_dir": skills_dir,
                       "skills": [s.to_dict() if hasattr(s, 'to_dict') else s for s in skills]}, f)
```

- [ ] **Step 2: Verify cache works**

Run twice:
```bash
cd /Users/daobanxiang/myproject/TARS/backend
time python -c "from tars.skills import skill_registry; print(len(skill_registry.list_enabled()))"
time python -c "from tars.skills import skill_registry; print(len(skill_registry.list_enabled()))"
```
Expected: Second run faster (cache hit)

- [ ] **Step 3: Commit**

```bash
git add backend/tars/skills/loader.py
git commit -m "feat(perf): add skills manifest cache for faster second startup"
```

---

## Task 4: Connection Pool — LLM 连接复用

**Files:**
- Create: `backend/tars/models/connection_pool.py`
- Create: `backend/tests/test_connection_pool.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_connection_pool.py
import pytest
import asyncio
from tars.models.connection_pool import LLMConnectionPool

class TestConnectionPool:
    def setup_method(self):
        self.pool = LLMConnectionPool()

    def test_get_client_returns_httpx_client(self):
        client = self.pool.get_client("ollama:http://localhost:11434")
        assert client is not None
        assert hasattr(client, 'get')
        assert hasattr(client, 'post')

    def test_same_key_returns_same_client(self):
        c1 = self.pool.get_client("ollama:http://localhost:11434")
        c2 = self.pool.get_client("ollama:http://localhost:11434")
        assert c1 is c2

    def test_different_key_returns_different_client(self):
        c1 = self.pool.get_client("ollama:http://localhost:11434")
        c2 = self.pool.get_client("custom:https://api.deepseek.com")
        assert c1 is not c2

    def test_close_all(self):
        self.pool.get_client("ollama:http://localhost:11434")
        self.pool.get_client("custom:https://api.deepseek.com")
        # Should not raise
        asyncio.run(self.pool.close_all())
        assert len(self.pool._clients) == 0

    def test_pool_config_defaults(self):
        client = self.pool.get_client("test:http://localhost:8000")
        limits = client._pool._max_connections
        assert limits == 10  # default max_connections
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_connection_pool.py -v`
Expected: FAIL (import error)

- [ ] **Step 3: Implement connection pool**

```python
# backend/tars/models/connection_pool.py
import httpx
from typing import Dict

class LLMConnectionPool:
    """Provider-level httpx.AsyncClient reuse pool."""

    def __init__(self, max_connections: int = 10, max_keepalive: int = 5,
                 keepalive_expiry: float = 300, connect_timeout: float = 5,
                 read_timeout: float = 120):
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._max_connections = max_connections
        self._max_keepalive = max_keepalive
        self._keepalive_expiry = keepalive_expiry
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout

    def get_client(self, provider_key: str) -> httpx.AsyncClient:
        if provider_key not in self._clients:
            self._clients[provider_key] = httpx.AsyncClient(
                limits=httpx.Limits(
                    max_connections=self._max_connections,
                    max_keepalive_connections=self._max_keepalive,
                    keepalive_expiry=self._keepalive_expiry,
                ),
                timeout=httpx.Timeout(
                    connect=self._connect_timeout,
                    read=self._read_timeout,
                    write=30.0,
                    pool=10.0,
                ),
            )
        return self._clients[provider_key]

    async def close_all(self):
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

# Global singleton
connection_pool = LLMConnectionPool()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_connection_pool.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/tars/models/connection_pool.py backend/tests/test_connection_pool.py
git commit -m "feat(perf): implement LLM connection pool with httpx reuse"
```

---

## Task 5: Integrate Connection Pool into Providers

**Files:**
- Modify: `backend/tars/models/ollama.py`
- Modify: `backend/tars/models/custom.py`
- Modify: `backend/tars/models/openrouter.py`
- Modify: `backend/tars/main.py`

- [ ] **Step 1: Update OllamaProvider to use pool**

In `backend/tars/models/ollama.py`, replace per-request client creation:

```python
# Replace:
#   async with httpx.AsyncClient() as client:
#       response = await client.post(...)
# With:
from .connection_pool import connection_pool

class OllamaProvider:
    def __init__(self, model, base_url="http://localhost:11434"):
        self.base_url = base_url
        self._pool_key = f"ollama:{base_url}"
        # ...

    @property
    def client(self) -> httpx.AsyncClient:
        return connection_pool.get_client(self._pool_key)

    async def chat(self, messages, tools=None, **kwargs):
        response = await self.client.post(f"{self.base_url}/api/chat", json=payload)
        # ... rest of logic unchanged
```

- [ ] **Step 2: Update CustomProvider similarly**

In `backend/tars/models/custom.py`:
```python
from .connection_pool import connection_pool

# Use: connection_pool.get_client(f"custom:{self.base_url}")
```

- [ ] **Step 3: Update OpenRouterProvider similarly**

In `backend/tars/models/openrouter.py`:
```python
from .connection_pool import connection_pool

# Use: connection_pool.get_client(f"openrouter:{self.base_url}")
```

- [ ] **Step 4: Add shutdown hook in main.py**

```python
# In backend/tars/main.py
from tars.models.connection_pool import connection_pool

@app.on_event("shutdown")
async def shutdown_event():
    await connection_pool.close_all()
```

- [ ] **Step 5: Run existing tests for regression**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add backend/tars/models/ollama.py backend/tars/models/custom.py backend/tars/models/openrouter.py backend/tars/main.py
git commit -m "feat(perf): integrate connection pool into all LLM providers"
```

---

## Task 6: Prompt Cache — System Prompt 缓存

**Files:**
- Create: `backend/tars/cache/__init__.py`
- Create: `backend/tars/cache/prompt_cache.py`
- Create: `backend/tests/test_prompt_cache.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_prompt_cache.py
import pytest
import time
from tars.cache.prompt_cache import PromptCache

class TestPromptCache:
    def setup_method(self):
        self.cache = PromptCache()

    def test_get_or_build_caches_result(self):
        call_count = 0
        def builder():
            nonlocal call_count
            call_count += 1
            return "built_value"

        r1 = self.cache.get_or_build("key1", builder, ttl=60)
        r2 = self.cache.get_or_build("key1", builder, ttl=60)
        assert r1 == "built_value"
        assert r2 == "built_value"
        assert call_count == 1  # Builder called only once

    def test_ttl_expiry(self):
        self.cache.get_or_build("key2", lambda: "old", ttl=0)
        time.sleep(0.01)
        result = self.cache.get_or_build("key2", lambda: "new", ttl=0)
        assert result == "new"

    def test_invalidate_exact_key(self):
        self.cache.get_or_build("session:abc:core", lambda: "v1", ttl=60)
        self.cache.invalidate("session:abc:core")
        result = self.cache.get_or_build("session:abc:core", lambda: "v2", ttl=60)
        assert result == "v2"

    def test_invalidate_pattern(self):
        self.cache.get_or_build("session:abc:core", lambda: "v1", ttl=60)
        self.cache.get_or_build("session:abc:skills", lambda: "v1", ttl=60)
        self.cache.get_or_build("session:xyz:core", lambda: "v1", ttl=60)
        self.cache.invalidate_pattern("session:abc:*")
        # abc entries invalidated
        r1 = self.cache.get_or_build("session:abc:core", lambda: "v2", ttl=60)
        r2 = self.cache.get_or_build("session:xyz:core", lambda: "v2", ttl=60)
        assert r1 == "v2"  # Rebuilt
        assert r2 == "v1"  # Still cached

    def test_global_invalidate(self):
        self.cache.get_or_build("a", lambda: "1", ttl=60)
        self.cache.get_or_build("b", lambda: "2", ttl=60)
        self.cache.invalidate_all()
        r1 = self.cache.get_or_build("a", lambda: "new1", ttl=60)
        assert r1 == "new1"

    def test_stats(self):
        self.cache.get_or_build("k", lambda: "v", ttl=60)
        self.cache.get_or_build("k", lambda: "v", ttl=60)
        stats = self.cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_prompt_cache.py -v`
Expected: FAIL (import error)

- [ ] **Step 3: Implement prompt cache**

```python
# backend/tars/cache/__init__.py
from .prompt_cache import PromptCache, prompt_cache

__all__ = ["PromptCache", "prompt_cache"]
```

```python
# backend/tars/cache/prompt_cache.py
import time
import fnmatch
from typing import Callable, Dict, Optional, Any
from dataclasses import dataclass

@dataclass
class CacheEntry:
    value: str
    expires_at: float

class PromptCache:
    def __init__(self):
        self._store: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0

    def get_or_build(self, key: str, builder: Callable[[], str], ttl: int) -> str:
        entry = self._store.get(key)
        if entry and time.time() < entry.expires_at:
            self._hits += 1
            return entry.value

        self._misses += 1
        value = builder()
        self._store[key] = CacheEntry(value=value, expires_at=time.time() + ttl)
        return value

    def invalidate(self, key: str):
        self._store.pop(key, None)

    def invalidate_pattern(self, pattern: str):
        keys_to_remove = [k for k in self._store if fnmatch.fnmatch(k, pattern)]
        for k in keys_to_remove:
            del self._store[k]

    def invalidate_all(self):
        self._store.clear()

    def stats(self) -> Dict[str, Any]:
        return {"hits": self._hits, "misses": self._misses,
                "size": len(self._store), "hit_rate": self._hits / max(1, self._hits + self._misses)}

# Global singleton
prompt_cache = PromptCache()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_prompt_cache.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/tars/cache/__init__.py backend/tars/cache/prompt_cache.py backend/tests/test_prompt_cache.py
git commit -m "feat(perf): implement TTL-based prompt cache with pattern invalidation"
```

---

## Task 7: Integrate Prompt Cache into Agent

**Files:**
- Modify: `backend/tars/agent/agent.py`
- Modify: `backend/tars/memory/core_memory.py`

- [ ] **Step 1: Use cache for system prompt assembly in agent**

In `backend/tars/agent/agent.py`, find where system prompt is built and wrap with cache:

```python
from ..cache.prompt_cache import prompt_cache

# In the method that builds system prompt:
def _build_system_prompt(self, session_id: str, tenant_id: str, ...):
    # tools_schema: global, never expires
    tools_schema = prompt_cache.get_or_build(
        "global:tools_schema",
        lambda: self._generate_tools_schema(),
        ttl=86400,  # 24h (effectively permanent until restart)
    )

    # persona: per tenant, 1h TTL
    persona = prompt_cache.get_or_build(
        f"tenant:{tenant_id}:persona",
        lambda: self._load_persona(tenant_id),
        ttl=3600,
    )

    # core_memory: per session, 60s TTL
    core_mem = prompt_cache.get_or_build(
        f"session:{session_id}:core_memory",
        lambda: self._load_core_memory(tenant_id),
        ttl=60,
    )

    return f"{persona}\n\n{core_mem}\n\n{tools_schema}"
```

- [ ] **Step 2: Add cache invalidation on core memory write**

In `backend/tars/memory/core_memory.py`, after `_save_block`:

```python
from ..cache.prompt_cache import prompt_cache

# After saving a core memory block:
prompt_cache.invalidate_pattern(f"session:*:core_memory")
prompt_cache.invalidate_pattern(f"tenant:{self.tenant_id}:persona")
```

- [ ] **Step 3: Run tests for regression**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/tars/agent/agent.py backend/tars/memory/core_memory.py
git commit -m "feat(perf): integrate prompt cache into agent system prompt assembly"
```

---

## Task 8: Rate Limiter — 并发限流

**Files:**
- Create: `backend/tars/concurrency/__init__.py`
- Create: `backend/tars/concurrency/limiter.py`
- Create: `config/concurrency.yaml`
- Create: `backend/tests/test_limiter.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_limiter.py
import pytest
import asyncio
from tars.concurrency.limiter import LLMRateLimiter

class TestRateLimiter:
    def setup_method(self):
        self.limiter = LLMRateLimiter(max_concurrent=2, per_user_max=1, queue_timeout=2)

    @pytest.mark.asyncio
    async def test_acquire_within_limit(self):
        acquired = await self.limiter.acquire("user1", "ollama")
        assert acquired is True
        self.limiter.release("user1", "ollama")

    @pytest.mark.asyncio
    async def test_per_user_limit(self):
        await self.limiter.acquire("user1", "ollama")
        # Second acquire for same user should block/timeout
        acquired = await self.limiter.acquire("user1", "ollama")
        assert acquired is False
        self.limiter.release("user1", "ollama")

    @pytest.mark.asyncio
    async def test_different_users_concurrent(self):
        a1 = await self.limiter.acquire("user1", "ollama")
        a2 = await self.limiter.acquire("user2", "ollama")
        assert a1 is True
        assert a2 is True
        self.limiter.release("user1", "ollama")
        self.limiter.release("user2", "ollama")

    @pytest.mark.asyncio
    async def test_global_limit_blocks_third_user(self):
        await self.limiter.acquire("user1", "ollama")
        await self.limiter.acquire("user2", "ollama")
        # Third user exceeds global max_concurrent=2
        acquired = await self.limiter.acquire("user3", "ollama")
        assert acquired is False
        self.limiter.release("user1", "ollama")
        self.limiter.release("user2", "ollama")

    @pytest.mark.asyncio
    async def test_release_allows_next(self):
        await self.limiter.acquire("user1", "ollama")
        await self.limiter.acquire("user2", "ollama")
        self.limiter.release("user1", "ollama")
        # Now user3 can acquire
        acquired = await self.limiter.acquire("user3", "ollama")
        assert acquired is True
        self.limiter.release("user2", "ollama")
        self.limiter.release("user3", "ollama")

    def test_queue_position(self):
        pos = self.limiter.queue_position("user1", "ollama")
        assert pos == 0  # No queue
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_limiter.py -v`
Expected: FAIL (import error)

- [ ] **Step 3: Implement rate limiter**

```python
# backend/tars/concurrency/__init__.py
from .limiter import LLMRateLimiter, rate_limiter

__all__ = ["LLMRateLimiter", "rate_limiter"]
```

```python
# backend/tars/concurrency/limiter.py
import asyncio
from typing import Dict, Set

class LLMRateLimiter:
    def __init__(self, max_concurrent: int = 2, per_user_max: int = 1, queue_timeout: float = 60):
        self._max_concurrent = max_concurrent
        self._per_user_max = per_user_max
        self._queue_timeout = queue_timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._user_counts: Dict[str, int] = {}
        self._waiters: list = []

    async def acquire(self, tenant_id: str, provider_key: str) -> bool:
        # Check per-user limit
        current = self._user_counts.get(tenant_id, 0)
        if current >= self._per_user_max:
            return False

        # Try global semaphore with timeout
        try:
            acquired = await asyncio.wait_for(self._semaphore.acquire(), timeout=self._queue_timeout)
            if acquired:
                self._user_counts[tenant_id] = current + 1
                return True
        except asyncio.TimeoutError:
            return False
        return False

    def release(self, tenant_id: str, provider_key: str):
        current = self._user_counts.get(tenant_id, 0)
        if current > 0:
            self._user_counts[tenant_id] = current - 1
        self._semaphore.release()

    def queue_position(self, tenant_id: str, provider_key: str) -> int:
        # Approximate: how many waiters are ahead
        waiting = self._max_concurrent - self._semaphore._value
        return max(0, waiting)

# Global singleton (configured at startup)
rate_limiter: LLMRateLimiter = None

def init_rate_limiter(max_concurrent=2, per_user_max=1, queue_timeout=60) -> LLMRateLimiter:
    global rate_limiter
    rate_limiter = LLMRateLimiter(max_concurrent, per_user_max, queue_timeout)
    return rate_limiter
```

- [ ] **Step 4: Create concurrency config**

```yaml
# config/concurrency.yaml
providers:
  ollama:
    max_concurrent: 2
    per_user_max: 1
    queue_timeout: 60
  custom:
    max_concurrent: 5
    per_user_max: 2
    queue_timeout: 30
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_limiter.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/tars/concurrency/__init__.py backend/tars/concurrency/limiter.py config/concurrency.yaml backend/tests/test_limiter.py
git commit -m "feat(perf): implement LLM rate limiter with per-user fair scheduling"
```

---

## Task 9: Integrate Rate Limiter into Agent

**Files:**
- Modify: `backend/tars/agent/agent.py`
- Modify: `backend/tars/main.py`

- [ ] **Step 1: Add acquire/release around LLM calls in agent**

In `backend/tars/agent/agent.py`, wrap the LLM call in `handle_message`:

```python
from ..concurrency.limiter import rate_limiter

# Before LLM call:
if rate_limiter:
    acquired = await rate_limiter.acquire(tenant_id, self._pool_key())
    if not acquired:
        await channel.send(session_id, {
            "type": "error",
            "session_id": session_id,
            "message": "系统繁忙，请稍后重试",
            "code": "rate_limited",
            "timestamp": now_iso(),
        })
        return

try:
    # ... existing LLM call logic ...
    pass
finally:
    if rate_limiter:
        rate_limiter.release(tenant_id, self._pool_key())
```

- [ ] **Step 2: Initialize rate limiter in main.py**

```python
# In backend/tars/main.py startup
import yaml
from pathlib import Path
from tars.concurrency.limiter import init_rate_limiter

config_path = Path(__file__).parent.parent / "config" / "concurrency.yaml"
if config_path.exists():
    with open(config_path) as f:
        conc_config = yaml.safe_load(f)
    ollama_cfg = conc_config.get("providers", {}).get("ollama", {})
    init_rate_limiter(
        max_concurrent=ollama_cfg.get("max_concurrent", 2),
        per_user_max=ollama_cfg.get("per_user_max", 1),
        queue_timeout=ollama_cfg.get("queue_timeout", 60),
    )
```

- [ ] **Step 3: Run tests for regression**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/tars/agent/agent.py backend/tars/main.py
git commit -m "feat(perf): integrate rate limiter into agent LLM call path"
```

---

## Task 10: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_prompt_cache.py tests/test_limiter.py tests/test_connection_pool.py -v`
Expected: ALL PASS (17+ tests)

- [ ] **Step 2: Measure startup time**

```bash
cd /Users/daobanxiang/myproject/TARS/backend
time python -c "from tars.main import app; print('startup ok')"
```
Expected: < 3 seconds

- [ ] **Step 3: Run regression tests**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/ -v --tb=short`
Expected: No regressions

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test(perf): verify Phase 2 performance improvements"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Lazy import utility | — |
| 2 | Startup optimization | — |
| 3 | Skills manifest cache | — |
| 4 | Connection pool | 5 |
| 5 | Provider integration | — |
| 6 | Prompt cache | 6 |
| 7 | Cache integration | — |
| 8 | Rate limiter | 6 |
| 9 | Limiter integration | — |
| 10 | Final verification | — |
| **Total** | | **17+** |
