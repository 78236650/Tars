"""Chroma 向量数据库客户端封装"""
import os
import uuid
from typing import List, Dict, Any, Optional, Tuple

from tars.memory.embeddings import EmbeddingProvider, LocalEmbeddingProvider
from tars.org import ORG_ID
from tars.vectorstore.scope import collection_full_name


class ChromaVectorStore:
    """Chroma 向量数据库封装，支持多租户"""

    def __init__(
        self,
        persist_directory: str = None,
        embedding_provider: EmbeddingProvider = None,
    ):
        if persist_directory is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            persist_directory = os.path.join(base_dir, "data", "vectorstore")

        os.makedirs(persist_directory, exist_ok=True)
        self.persist_directory = persist_directory
        self._embedding_provider = embedding_provider

        # 延迟导入 chromadb，避免启动时加载失败影响整个应用
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=persist_directory)
        except ImportError:
            self._client = None

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def _get_collection(self, tenant_id: str = "default", collection_name: str = "memories") -> Any:
        """获取或创建 collection（v5: org-scoped via ORG_ID suffix）。"""
        if not self.is_available:
            raise RuntimeError("Chroma client not available")

        full_name = collection_full_name(collection_name, tenant_id)

        try:
            collection = self._client.get_collection(name=full_name)
        except Exception:
            collection = self._client.create_collection(
                name=full_name,
                metadata={"org_id": ORG_ID, "collection_type": collection_name},
            )
        return collection

    def get_collection(self, collection_name: str = "memories", tenant_id: str = "default") -> Any:
        """公开获取 collection，便于知识库索引等场景复用。"""
        return self._get_collection(tenant_id=tenant_id, collection_name=collection_name)

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
        tenant_id: str = "default",
        collection_name: str = "memories",
    ) -> List[str]:
        """
        添加文档到向量数据库
        返回: 文档 ID 列表
        """
        if not documents:
            return []

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]

        # 生成 embedding
        embeddings = None
        if self._embedding_provider:
            try:
                embeddings = self._embedding_provider.encode(documents)
            except Exception as e:
                print(f"[ChromaVectorStore] Embedding generation failed: {e}")

        collection = self._get_collection(tenant_id, collection_name)

        # 分批添加（避免单次请求过大）
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]
            batch_meta = metadatas[i:i + batch_size]
            batch_embed = embeddings[i:i + batch_size] if embeddings else None

            kwargs = {
                "documents": batch_docs,
                "metadatas": batch_meta,
                "ids": batch_ids,
            }
            if batch_embed:
                kwargs["embeddings"] = batch_embed

            collection.add(**kwargs)

        return ids

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        tenant_id: str = "default",
        collection_name: str = "memories",
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        向量相似度查询
        返回: [{id, document, metadata, distance}]
        """
        collection = self._get_collection(tenant_id, collection_name)

        query_embedding = None
        if self._embedding_provider:
            try:
                vectors = self._embedding_provider.encode([query_text])
                query_embedding = vectors[0] if vectors else None
            except Exception as e:
                print(f"[ChromaVectorStore] Query embedding failed: {e}")

        kwargs = {
            "query_texts": [query_text] if query_embedding is None else None,
            "query_embeddings": [query_embedding] if query_embedding else None,
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if filter_dict:
            kwargs["where"] = filter_dict

        # 移除 None 值
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        results = collection.query(**kwargs)

        # 格式化结果
        formatted = []
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i in range(len(ids)):
            formatted.append({
                "id": ids[i],
                "document": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "distance": distances[i] if i < len(distances) else 0.0,
            })

        return formatted

    def delete(
        self,
        ids: Optional[List[str]] = None,
        tenant_id: str = "default",
        collection_name: str = "memories",
        where: Optional[Dict[str, Any]] = None,
    ) -> None:
        """按 ids 或 metadata where 条件删除。两者至少一项。"""
        collection = self._get_collection(tenant_id, collection_name)
        if ids:
            collection.delete(ids=ids)
        elif where:
            collection.delete(where=where)

    def delete_collection(self, tenant_id: str = "default", collection_name: str = "memories") -> None:
        """删除整个 collection"""
        full_name = collection_full_name(collection_name, tenant_id)
        try:
            self._client.delete_collection(name=full_name)
        except Exception:
            pass

    def count(self, tenant_id: str = "default", collection_name: str = "memories") -> int:
        """获取 collection 中文档数量"""
        try:
            collection = self._get_collection(tenant_id, collection_name)
            return collection.count()
        except Exception:
            return 0

    def get_by_ids(
        self,
        ids: List[str],
        tenant_id: str = "default",
        collection_name: str = "memories",
    ) -> List[Dict[str, Any]]:
        """根据 ID 获取文档"""
        collection = self._get_collection(tenant_id, collection_name)
        results = collection.get(
            ids=ids,
            include=["documents", "metadatas"],
        )

        formatted = []
        for i, doc_id in enumerate(results.get("ids", [])):
            formatted.append({
                "id": doc_id,
                "document": results["documents"][i] if i < len(results["documents"]) else "",
                "metadata": results["metadatas"][i] if i < len(results["metadatas"]) else {},
            })
        return formatted
