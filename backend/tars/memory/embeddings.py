"""嵌入向量 Provider"""
import struct
from abc import ABC, abstractmethod
from typing import List, Optional


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dim(self) -> int:
        """向量维度"""
        pass

    @abstractmethod
    def encode(self, texts: List[str]) -> List[List[float]]:
        """批量编码"""
        pass


class LocalEmbeddingProvider(EmbeddingProvider):
    """本地 sentence-transformers 模型（默认 bge-small-zh-v1.5）"""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        self.model_name = model_name
        self._model = None
        self._dim = 512  # bge-small 维度

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            # 获取实际维度
            self._dim = self._model.get_sentence_embedding_dimension()

    @property
    def dim(self) -> int:
        return self._dim

    def encode(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        self._load_model()
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return vectors.tolist()


class OllamaEmbeddingProvider(EmbeddingProvider):
    """调用 Ollama embeddings API"""

    def __init__(self, model: str = "bge-m3", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self._dim = 1024  # bge-m3 维度

    @property
    def dim(self) -> int:
        return self._dim

    def encode(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        import httpx
        results = []
        with httpx.Client(timeout=30.0) as client:
            for text in texts:
                resp = client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                resp.raise_for_status()
                data = resp.json()
                vec = data.get("embedding", [])
                results.append(vec)
                if vec:
                    self._dim = len(vec)
        return results


def serialize_vector(vec: List[float]) -> bytes:
    """向量 → bytes（float32）"""
    return struct.pack(f"{len(vec)}f", *vec)


def deserialize_vector(data: bytes) -> List[float]:
    """bytes → 向量"""
    if not data:
        return []
    n = len(data) // 4
    return list(struct.unpack(f"{n}f", data))
