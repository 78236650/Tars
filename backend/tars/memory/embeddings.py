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
    """本地 sentence-transformers 模型（默认 bge-small-zh-v1.5）。

    v4.0.0: 模型延迟加载，仅在首次 encode 时才加载到内存。
    """

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        import os
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        self.model_name = model_name
        self._dim = 512
        self._model = None

    def _ensure_loaded(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._dim = self._model.get_embedding_dimension()

    @property
    def dim(self) -> int:
        return self._dim

    def encode(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        self._ensure_loaded()
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


class EmbeddingManager:
    """管理 embedding provider 的运行时切换"""

    def __init__(self, provider: EmbeddingProvider = None):
        self.provider = provider
        self._provider_type = "local"
        self._model_name = "BAAI/bge-small-zh-v1.5"

    def get_info(self) -> dict:
        return {
            "provider": self._provider_type,
            "model": self._model_name,
            "dimension": self.provider.dim if self.provider else 0,
        }

    def reinitialize(self, provider: str, model: str) -> dict:
        """切换 embedding provider"""
        old_dim = self.provider.dim if self.provider else 0
        try:
            if provider == "local":
                new_provider = LocalEmbeddingProvider(model)
            elif provider == "ollama":
                new_provider = OllamaEmbeddingProvider(model=model)
            else:
                return {"success": False, "error": f"不支持的 provider: {provider}"}

            self.provider = new_provider
            self._provider_type = provider
            self._model_name = model
            new_dim = new_provider.dim
            warning = None
            if old_dim and new_dim != old_dim:
                warning = f"维度从 {old_dim} 变为 {new_dim}，建议重建索引"
            return {"success": True, "dimension": new_dim, "warning": warning}
        except Exception as e:
            return {"success": False, "error": str(e)}


def serialize_vector(vec: List[float]) -> bytes:
    """向量 → bytes（float32）"""
    return struct.pack(f"{len(vec)}f", *vec)


def deserialize_vector(data: bytes) -> List[float]:
    """bytes → 向量"""
    if not data:
        return []
    n = len(data) // 4
    return list(struct.unpack(f"{n}f", data))
