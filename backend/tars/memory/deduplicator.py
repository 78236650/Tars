"""记忆去重器"""
import numpy as np
from typing import List, Optional, Tuple


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """计算余弦相似度"""
    a_arr = np.array(a, dtype=np.float32)
    b_arr = np.array(b, dtype=np.float32)
    dot = np.dot(a_arr, b_arr)
    norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    if norm == 0:
        return 0.0
    return float(dot / norm)


def jaccard_similarity(a: str, b: str) -> float:
    """基于字符 bigram 的 Jaccard 相似度"""
    if not a or not b:
        return 0.0
    set_a = set(a[i:i+2] for i in range(len(a) - 1))
    set_b = set(b[i:i+2] for i in range(len(b) - 1))
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


class MemoryDeduplicator:
    """记忆去重：精确匹配 → 包含匹配 → 语义相似"""

    def __init__(self, embedding_provider=None, threshold: float = 0.85):
        self.embedding_provider = embedding_provider
        self.threshold = threshold

    def is_duplicate(self, new_content: str, existing_memories: list) -> Tuple[bool, Optional[object]]:
        """
        返回 (is_dup, update_target)
        - (True, None) → 完全重复，跳过
        - (True, Memory) → 新内容更完整，应更新该记忆
        - (False, None) → 不重复，保存新记忆
        """
        new_stripped = new_content.strip()

        for mem in existing_memories:
            existing = mem.content.strip()

            # 1. 精确匹配
            if new_stripped == existing:
                return (True, None)

            # 2. 包含匹配
            if new_stripped in existing:
                return (True, None)
            if existing in new_stripped and len(new_stripped) > len(existing):
                return (True, mem)  # 新的更完整，更新旧的

            # 3. 文本相似度（Jaccard bigram）
            sim = jaccard_similarity(new_stripped, existing)
            if sim > self.threshold:
                if len(new_stripped) > len(existing):
                    return (True, mem)
                return (True, None)

        # 4. 语义相似度（如果有嵌入）
        if self.embedding_provider and existing_memories:
            try:
                new_vec = self.embedding_provider.encode([new_content])[0]
                for mem in existing_memories:
                    if hasattr(mem, "embedding") and mem.embedding:
                        sim = cosine_similarity(new_vec, mem.embedding)
                        if sim > self.threshold:
                            return (True, None)
            except Exception:
                pass

        return (False, None)
