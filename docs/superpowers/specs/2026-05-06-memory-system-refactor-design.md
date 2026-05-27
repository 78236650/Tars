---
doc_type: spec
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# 记忆系统重构设计 — LLM 提取 + 语义搜索

## 概述

重构 TARS 记忆系统，解决当前正则提取 bug 导致记忆无效的问题，对齐 Hermes-Agent 的核心记忆能力。

**核心改进**：
1. LLM 驱动的记忆提取（替代有 bug 的正则）
2. 去重机制（避免重复记忆）
3. 嵌入式语义搜索（bge-small-zh-v1.5 + 混合检索）

## 当前问题

- `MemoryExtractor` 正则 `(.+?)。?` 只匹配 1-3 字符（非贪婪 + 可选句号 bug）
- 只支持中文固定句式，大量有价值信息被忽略
- 无去重，同一信息重复保存
- 纯 FTS 关键词搜索，语义不匹配时检索失败

## 新架构

```
对话结束
    ↓
LLMMemoryExtractor.extract(conversation, provider)
    ↓ (失败时 fallback 到 RegexExtractor)
MemoryDeduplicator.is_duplicate(new, existing)
    ↓ (非重复)
EmbeddingProvider.encode(content) → 512维向量
    ↓
Database.add_memory(content, category, embedding)

检索时：
    query → EmbeddingProvider.encode(query) → 查询向量
    ↓
    HybridSearch(语义 top-10 + FTS top-10) → 合并排序
    ↓
    注入 system prompt
```

## 模块设计

### 目录结构

```
tars/
├── memory/
│   ├── __init__.py
│   ├── extractor.py        # LLMMemoryExtractor + RegexExtractor
│   ├── deduplicator.py     # MemoryDeduplicator
│   ├── embeddings.py       # EmbeddingProvider (Local bge-small + Ollama)
│   ├── search.py           # HybridSearch (语义 + FTS)
│   └── manager.py          # MemoryManager (整合以上模块)
```

### 1. LLMMemoryExtractor (extractor.py)

```python
class LLMMemoryExtractor:
    EXTRACTION_PROMPT = """从以下对话中提取值得长期记住的信息。只提取明确表达的事实，不要推测。

输出 JSON 数组，每条记忆包含：
- content: 简洁的事实描述（一句话）
- category: user_preference / important_decision / project_record / general

只输出 JSON，不要其他内容。如果没有值得记住的信息，输出空数组 []。

对话内容：
{conversation}"""

    async def extract(self, conversation: str, provider) -> List[dict]:
        """调用 LLM 提取记忆，失败时 fallback 到正则"""
        try:
            response = await provider.chat([...], stream=False)
            return parse_json(response.content)
        except Exception:
            return RegexExtractor().extract(conversation)


class RegexExtractor:
    """修复后的正则提取器（fallback）"""
    patterns = {
        'user_preference': [
            r'我喜欢([^。\n]+)',
            r'我偏好([^。\n]+)',
            r'我通常([^。\n]+)',
            r'不要([^。\n]+)',
            r'I prefer ([^.\n]+)',
            r'I like ([^.\n]+)',
        ],
        'important_decision': [
            r'决定([^。\n]+)',
            r'选择([^。\n]+)作为',
            r'采用([^。\n]+)',
            r'We decided ([^.\n]+)',
        ],
        'project_record': [
            r'完成了([^。\n]+)',
            r'启动了([^。\n]+)',
            r'使用了([^。\n]+)',
            r'Completed ([^.\n]+)',
        ]
    }
```

### 2. MemoryDeduplicator (deduplicator.py)

```python
class MemoryDeduplicator:
    def __init__(self, embedding_provider=None):
        self.embedding_provider = embedding_provider

    def is_duplicate(self, new_content: str, existing_memories: List[Memory], threshold: float = 0.8) -> tuple[bool, Optional[Memory]]:
        """
        返回 (is_dup, existing_match)
        - is_dup=True, match=None → 跳过
        - is_dup=True, match=Memory → 更新已有记忆
        - is_dup=False → 保存新记忆
        """
        # 1. 精确匹配
        for mem in existing_memories:
            if new_content.strip() == mem.content.strip():
                return (True, None)

        # 2. 包含匹配
        for mem in existing_memories:
            if new_content in mem.content or mem.content in new_content:
                longer = new_content if len(new_content) > len(mem.content) else None
                return (True, mem if longer else None)

        # 3. 语义相似度（如果有嵌入 provider）
        if self.embedding_provider:
            new_vec = self.embedding_provider.encode([new_content])[0]
            for mem in existing_memories:
                if mem.embedding:
                    sim = cosine_similarity(new_vec, mem.embedding)
                    if sim > threshold:
                        return (True, None)

        return (False, None)
```

### 3. EmbeddingProvider (embeddings.py)

```python
class EmbeddingProvider(ABC):
    @abstractmethod
    def encode(self, texts: List[str]) -> List[List[float]]:
        pass

class LocalEmbeddingProvider(EmbeddingProvider):
    """本地 bge-small-zh-v1.5"""
    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()

class OllamaEmbeddingProvider(EmbeddingProvider):
    """调用 Ollama embeddings API"""
    def __init__(self, model: str = "bge-m3", base_url: str = "http://localhost:11434"):
        ...

    def encode(self, texts: List[str]) -> List[List[float]]:
        # POST /api/embeddings
        ...
```

### 4. HybridSearch (search.py)

```python
class HybridSearch:
    def __init__(self, db: Database, embedding_provider: EmbeddingProvider):
        ...

    def search(self, query: str, limit: int = 5) -> List[Memory]:
        # 1. 语义搜索 top-10
        query_vec = self.embedding_provider.encode([query])[0]
        semantic_results = self._semantic_search(query_vec, limit=10)

        # 2. FTS 关键词搜索 top-10
        keyword_results = self.db.search_memories(query, limit=10)

        # 3. 合并去重，按 (相似度 * 0.6 + 重要性 * 0.4) 排序
        return self._merge_and_rank(semantic_results, keyword_results, limit)

    def _semantic_search(self, query_vec, limit) -> List[tuple[Memory, float]]:
        """遍历所有有 embedding 的记忆，计算余弦相似度"""
        all_memories = self.db.get_all_memories_with_embeddings()
        scored = []
        for mem in all_memories:
            sim = cosine_similarity(query_vec, mem.embedding)
            scored.append((mem, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]
```

### 5. MemoryManager (manager.py)

```python
class MemoryManager:
    def __init__(self, db, provider=None, embedding_provider=None):
        self.db = db
        self.extractor = LLMMemoryExtractor()
        self.deduplicator = MemoryDeduplicator(embedding_provider)
        self.search = HybridSearch(db, embedding_provider)
        self.embedding_provider = embedding_provider
        self.provider = provider

    async def extract_and_save(self, conversation: str) -> List[Memory]:
        """提取 → 去重 → 嵌入 → 保存"""
        extracted = await self.extractor.extract(conversation, self.provider)
        saved = []
        existing = self.db.get_recent_memories(50)

        for item in extracted:
            is_dup, match = self.deduplicator.is_duplicate(item['content'], existing)
            if is_dup and not match:
                continue
            if is_dup and match:
                # 更新已有记忆为更完整的版本
                self.db.update_memory(match.id, content=item['content'])
                continue

            # 生成嵌入
            embedding = None
            if self.embedding_provider:
                embedding = self.embedding_provider.encode([item['content']])[0]

            mem = self.db.add_memory(
                content=item['content'],
                category=item['category'],
                embedding=embedding,
            )
            saved.append(mem)
        return saved

    def get_context_for_query(self, query: str, limit: int = 5) -> str:
        """混合搜索获取相关记忆上下文"""
        memories = self.search.search(query, limit)
        if not memories:
            return ""
        parts = ["## 相关记忆"]
        for mem in memories:
            parts.append(f"- [{mem.category}] {mem.content}")
        return "\n".join(parts)
```

## 数据库变更

```sql
ALTER TABLE memories ADD COLUMN embedding BLOB;
```

- 已有记忆的 embedding 为 NULL
- 首次搜索时检测到 NULL → 异步补齐嵌入向量

## 修改的文件

- `tars/database/base.py` — Memory dataclass 增加 embedding 字段，新增 `get_all_memories_with_embeddings()`、`update_memory()` 方法
- `tars/agent/agent.py` — `extract_and_save` 改为 `await` + 传 provider
- `tars/tools/builtin/memory.py` — search 改用新 MemoryManager
- `tars/main.py` — 初始化 EmbeddingProvider + 新 MemoryManager，注入 Agent

## 删除的文件

- `tars/database/memory.py` — MemoryExtractor 和旧 MemoryManager 迁移到 `tars/memory/`

## 依赖

- `sentence-transformers` — 用户已安装 bge-small-zh-v1.5
- `numpy` — 向量运算

## 实现阶段

1. Phase 1：`memory/` 模块骨架 + 数据库 schema 迁移
2. Phase 2：`LLMMemoryExtractor` + 正则 fallback
3. Phase 3：`MemoryDeduplicator`
4. Phase 4：`EmbeddingProvider`（本地 bge-small）
5. Phase 5：`HybridSearch` + 集成到 Agent + 测试

## 测试计划

- Extractor：LLM 成功/失败 fallback/空对话/中英文
- Deduplicator：精确重复/包含关系/语义相似/不相似
- Embedding：加载模型/编码/序列化/余弦相似度
- HybridSearch：语义匹配/关键词匹配/合并排序
- 集成：完整链路（对话 → 提取 → 去重 → 嵌入 → 保存 → 检索 → 注入）
