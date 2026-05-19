"""知识库索引器 — 文档 → 分块 → embedding → 向量索引"""
import os
from typing import Dict, Any

from .chunker import DocumentChunker
from .parsers import DocumentParser


class KnowledgeIndexer:
    """知识库文档索引器"""

    def __init__(
        self,
        vector_store,
        embedding_provider,
        db=None,
        chunk_size: int = 300,
        chunk_overlap: int = 100,
        document_parser: DocumentParser | None = None,
    ):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.db = db
        self.chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.document_parser = document_parser or DocumentParser()

    def index_document(
        self,
        text: str,
        doc_id: str,
        collection_id: str,
        file_name: str = "",
        file_type: str = "",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """
        索引单个文档
        返回: {doc_id, chunk_count, status}
        """
        if not text or not text.strip():
            return {"doc_id": doc_id, "chunk_count": 0, "status": "empty"}

        # 分块
        metadata_base = {
            "doc_id": doc_id,
            "collection_id": collection_id,
            "file_name": file_name,
            "file_type": file_type,
            "tenant_id": tenant_id,
        }
        chunks = self.chunker.chunk(text, metadata=metadata_base)

        if not chunks:
            return {"doc_id": doc_id, "chunk_count": 0, "status": "no_chunks"}

        # 写入向量数据库（前缀文件名提升检索关联度）
        prefix = f"[{file_name}] " if file_name else ""
        documents = [prefix + c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        ids = [f"{doc_id}_chunk_{c['chunk_index']}" for c in chunks]

        chroma_ok = bool(
            self.vector_store
            and getattr(self.vector_store, "is_available", False)
        )
        if chroma_ok:
            try:
                self.vector_store.add_documents(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids,
                    tenant_id=tenant_id,
                    collection_name=f"knowledge_{collection_id}",
                )
                return {
                    "doc_id": doc_id,
                    "chunk_count": len(chunks),
                    "status": "indexed",
                    "backend": "chroma",
                }
            except Exception as e:
                print(f"[KnowledgeIndexer] Chroma index failed, fallback to SQLite: {e}")

        if self.db is None:
            return {
                "doc_id": doc_id,
                "chunk_count": 0,
                "status": "error",
                "error": "向量库不可用且未配置 SQLite 回退",
            }

        try:
            from .sqlite_store import store_chunks

            stored = store_chunks(
                self.db,
                self.embedding_provider,
                chunks=chunks,
                doc_id=doc_id,
                collection_id=collection_id,
                tenant_id=tenant_id,
                file_name=file_name,
            )
            if stored <= 0:
                return {
                    "doc_id": doc_id,
                    "chunk_count": 0,
                    "status": "error",
                    "error": "未能写入任何文档分块",
                }
            print(f"[KnowledgeIndexer] Indexed {stored} chunks via SQLite (tenant={tenant_id})")
            return {
                "doc_id": doc_id,
                "chunk_count": stored,
                "status": "indexed",
                "backend": "sqlite",
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "doc_id": doc_id,
                "chunk_count": 0,
                "status": "error",
                "error": str(e),
            }

    def delete_document(
        self,
        doc_id: str,
        collection_id: str,
        tenant_id: str = "default",
    ) -> bool:
        """删除文档的所有 chunk"""
        try:
            if self.db is None:
                return False

            doc = self.db.get_document_file(doc_id)
            if not doc:
                return False

            chunk_count = int(doc.get("chunk_count") or 0)
            chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(chunk_count)]

            if chunk_ids and self.vector_store and getattr(self.vector_store, "is_available", False):
                collection_name = f"knowledge_{collection_id}"
                try:
                    if hasattr(self.vector_store, "delete"):
                        self.vector_store.delete(
                            ids=chunk_ids,
                            tenant_id=tenant_id,
                            collection_name=collection_name,
                        )
                    elif hasattr(self.vector_store, "get_collection"):
                        collection = self.vector_store.get_collection(
                            collection_name=collection_name,
                            tenant_id=tenant_id,
                        )
                        collection.delete(ids=chunk_ids)
                except Exception as e:
                    print(f"[KnowledgeIndexer] Chroma delete failed: {e}")

            if self.db is not None:
                try:
                    from .sqlite_store import delete_chunks
                    delete_chunks(self.db, doc_id)
                except Exception as e:
                    print(f"[KnowledgeIndexer] SQLite chunk delete failed: {e}")

            self.db.delete_document_file(doc_id)
            return True
        except Exception as e:
            print(f"[KnowledgeIndexer] 删除失败: {e}")
            return False

    def index_file(
        self,
        file_path: str,
        doc_id: str,
        collection_id: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """从文件路径读取并索引"""
        try:
            text = self.document_parser.parse(file_path)
        except Exception as e:
            return {"doc_id": doc_id, "chunk_count": 0, "status": "read_error", "error": str(e)}

        file_name = os.path.basename(file_path)
        file_type = os.path.splitext(file_name)[1].lower()

        return self.index_document(
            text=text,
            doc_id=doc_id,
            collection_id=collection_id,
            file_name=file_name,
            file_type=file_type,
            tenant_id=tenant_id,
        )
