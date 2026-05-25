"""知识库索引器 — 文档 → 分块 → embedding → 向量索引。

v4.3.1：在保留旧 `index_document(text=...)` passage-only 路径的同时，新增
`index_parsed(parsed, profile, ...)` 支持结构化解析 + 衍生 chunk 写入。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .chunker import DocumentChunker
from .config import get_chunk_profile, get_enrichment_config, load_knowledge_config
from .models import ChunkType, DocProfile, ParsedDocument
from .parsers import DocumentParser


class KnowledgeIndexer:
    """知识库文档索引器。"""

    def __init__(
        self,
        vector_store,
        embedding_provider,
        db=None,
        chunk_size: int = 300,
        chunk_overlap: int = 100,
        document_parser: DocumentParser | None = None,
        knowledge_config: dict | None = None,
    ):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.db = db
        self.knowledge_config = knowledge_config or load_knowledge_config()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.document_parser = document_parser or DocumentParser()

    def _chunker_for_doc_type(self, doc_type: str) -> DocumentChunker:
        profile = get_chunk_profile(doc_type or "generic")
        return DocumentChunker(
            chunk_size=profile["chunk_size"],
            chunk_overlap=profile["overlap"],
        )

    # ----- 旧 API：纯文本 passage 索引（兼容现有调用方）-----

    def index_document(
        self,
        text: str,
        doc_id: str,
        collection_id: str,
        file_name: str = "",
        file_type: str = "",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        if not text or not text.strip():
            return {"doc_id": doc_id, "chunk_count": 0, "status": "empty"}

        parsed = ParsedDocument(plain_text=text)
        return self.index_parsed(
            parsed=parsed,
            profile=None,
            doc_id=doc_id,
            collection_id=collection_id,
            file_name=file_name,
            file_type=file_type,
            tenant_id=tenant_id,
        )

    # ----- v4.3.1 新 API：结构化 + 画像 -----

    def index_parsed(
        self,
        parsed: ParsedDocument,
        profile: Optional[DocProfile],
        doc_id: str,
        collection_id: str,
        file_name: str = "",
        file_type: str = "",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """写入 passage + 衍生 chunk（doc_summary / section_summary / key_fact / synthetic_qa / glossary）。"""
        passage_chunks = self._build_passage_chunks(parsed, doc_id, collection_id, file_name, file_type, tenant_id)
        derived_chunks = self._build_derived_chunks(profile, doc_id, collection_id, file_name, file_type, tenant_id)
        chunks = derived_chunks + passage_chunks

        if not chunks:
            return {"doc_id": doc_id, "chunk_count": 0, "status": "no_chunks"}

        prefix = f"[{file_name}] " if file_name else ""
        documents = [prefix + c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        ids = [c["chunk_id"] for c in chunks]

        chroma_ok = bool(
            self.vector_store and getattr(self.vector_store, "is_available", False)
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
                    "passage_count": len(passage_chunks),
                    "derived_count": len(derived_chunks),
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
                "passage_count": len(passage_chunks),
                "derived_count": len(derived_chunks),
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

    def _build_passage_chunks(
        self,
        parsed: ParsedDocument,
        doc_id: str,
        collection_id: str,
        file_name: str,
        file_type: str,
        tenant_id: str,
    ) -> List[Dict[str, Any]]:
        """按 section 切 passage；无 section 时退化为纯文本切。"""
        doc_type = parsed.doc_type_hint or "generic"
        chunker = self._chunker_for_doc_type(doc_type)
        base_meta = {
            "doc_id": doc_id,
            "collection_id": collection_id,
            "file_name": file_name,
            "file_type": file_type,
            "tenant_id": tenant_id,
            "doc_type": doc_type,
            "chunk_type": ChunkType.PASSAGE,
        }

        out: List[Dict[str, Any]] = []
        running_idx = 0

        if parsed.sections:
            pieces = chunker.chunk_by_sections(parsed.sections, metadata=base_meta)
            for piece in pieces:
                meta = dict(piece.get("metadata") or base_meta)
                meta["chunk_type"] = ChunkType.PASSAGE
                out.append({
                    "text": piece["text"],
                    "metadata": meta,
                    "chunk_index": running_idx,
                    "chunk_id": f"{doc_id}_chunk_{running_idx}",
                })
                running_idx += 1
        else:
            for piece in chunker.chunk(parsed.plain_text, metadata=base_meta):
                meta = dict(piece.get("metadata") or base_meta)
                meta["chunk_index"] = running_idx
                out.append({
                    "text": piece["text"],
                    "metadata": meta,
                    "chunk_index": running_idx,
                    "chunk_id": f"{doc_id}_chunk_{running_idx}",
                })
                running_idx += 1

        total = len(out)
        for c in out:
            c["metadata"]["chunk_total"] = total
        return out

    def _build_derived_chunks(
        self,
        profile: Optional[DocProfile],
        doc_id: str,
        collection_id: str,
        file_name: str,
        file_type: str,
        tenant_id: str,
    ) -> List[Dict[str, Any]]:
        """从 DocProfile 衍生 doc_summary / section_summary / key_fact / synthetic_qa / glossary chunks。"""
        if profile is None:
            return []

        base_meta_common = {
            "doc_id": doc_id,
            "collection_id": collection_id,
            "file_name": file_name,
            "file_type": file_type,
            "tenant_id": tenant_id,
            "doc_type": profile.doc_type or "generic",
        }
        out: List[Dict[str, Any]] = []

        if profile.summary or profile.one_liner:
            text = "\n".join(filter(None, [profile.one_liner, profile.summary]))
            meta = dict(base_meta_common)
            meta.update({"chunk_type": ChunkType.DOC_SUMMARY, "chunk_index": 0})
            out.append({
                "text": text,
                "metadata": meta,
                "chunk_index": 0,
                "chunk_id": f"{doc_id}_summary_0",
            })

        for i, section in enumerate(profile.sections or []):
            if not section.summary:
                continue
            meta = dict(base_meta_common)
            meta.update({
                "chunk_type": ChunkType.SECTION_SUMMARY,
                "chunk_index": i,
                "section_id": section.section_id,
                "section_title": section.title,
                "parent_section_id": section.section_id,
                "page_or_slide": section.page_or_slide,
            })
            out.append({
                "text": f"{section.title}：{section.summary}".strip(),
                "metadata": meta,
                "chunk_index": i,
                "chunk_id": f"{doc_id}_section_{section.section_id or i}",
            })

        for i, fact in enumerate(profile.key_facts or []):
            text = fact if isinstance(fact, str) else str(fact)
            if not text.strip():
                continue
            meta = dict(base_meta_common)
            meta.update({"chunk_type": ChunkType.KEY_FACT, "chunk_index": i})
            out.append({
                "text": text,
                "metadata": meta,
                "chunk_index": i,
                "chunk_id": f"{doc_id}_keyfact_{i}",
            })

        for i, qa in enumerate(profile.qa_pairs or []):
            q = (qa.question or "").strip()
            a = (qa.answer or "").strip()
            if not q:
                continue
            meta = dict(base_meta_common)
            meta.update({"chunk_type": ChunkType.SYNTHETIC_QA, "chunk_index": i})
            out.append({
                "text": f"Q: {q}\nA: {a}",
                "metadata": meta,
                "chunk_index": i,
                "chunk_id": f"{doc_id}_qa_{i}",
            })

        for i, item in enumerate(profile.glossary or []):
            term = (item.term or "").strip()
            definition = (item.definition or "").strip()
            if not term:
                continue
            meta = dict(base_meta_common)
            meta.update({"chunk_type": ChunkType.GLOSSARY, "chunk_index": i})
            out.append({
                "text": f"{term}：{definition}",
                "metadata": meta,
                "chunk_index": i,
                "chunk_id": f"{doc_id}_glossary_{i}",
            })

        return out

    # ----- 删除（兼容 passage / 衍生 chunk）-----

    def delete_document(
        self,
        doc_id: str,
        collection_id: str,
        tenant_id: str = "default",
    ) -> bool:
        """删除文档的所有 chunk（passage + 衍生）。"""
        try:
            if self.db is None:
                return False

            doc = self.db.get_document_file(doc_id)
            if not doc:
                return False

            chroma_ok = bool(self.vector_store and getattr(self.vector_store, "is_available", False))
            if chroma_ok:
                collection_name = f"knowledge_{collection_id}"
                try:
                    if hasattr(self.vector_store, "delete"):
                        self.vector_store.delete(
                            where={"doc_id": doc_id},
                            tenant_id=tenant_id,
                            collection_name=collection_name,
                        )
                    elif hasattr(self.vector_store, "get_collection"):
                        collection = self.vector_store.get_collection(
                            collection_name=collection_name,
                            tenant_id=tenant_id,
                        )
                        collection.delete(where={"doc_id": doc_id})
                except Exception as e:
                    print(f"[KnowledgeIndexer] Chroma delete by doc_id failed: {e}")
                    # 兜底：按旧的 chunk_id 命名规则删 passage
                    try:
                        chunk_count = int(doc.get("chunk_count") or 0)
                        legacy_ids = [f"{doc_id}_chunk_{i}" for i in range(chunk_count)]
                        if hasattr(self.vector_store, "delete"):
                            self.vector_store.delete(
                                ids=legacy_ids,
                                tenant_id=tenant_id,
                                collection_name=collection_name,
                            )
                    except Exception:
                        pass

            try:
                from .sqlite_store import delete_chunks
                delete_chunks(self.db, doc_id)
            except Exception as e:
                print(f"[KnowledgeIndexer] SQLite chunk delete failed: {e}")

            try:
                from .profile_store import delete_profile
                delete_profile(self.db, doc_id)
            except Exception as e:
                print(f"[KnowledgeIndexer] profile delete failed: {e}")

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
        """从文件路径读取并索引（passage-only 兼容路径，深度入库由 api 层显式编排）。"""
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
