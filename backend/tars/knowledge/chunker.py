"""文档分块器 — 支持多种分块策略"""
import re
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import DocumentSection


class DocumentChunker:
    """文档分块器，支持固定长度、按段落、递归分块"""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        strategy: str = "recursive",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy

    def chunk(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        对文本进行分块
        返回: [{text, metadata, chunk_index, chunk_total}]
        """
        if not text or not text.strip():
            return []

        if self.strategy == "fixed":
            chunks = self._fixed_length_chunk(text)
        elif self.strategy == "paragraph":
            chunks = self._paragraph_chunk(text)
        elif self.strategy == "recursive":
            chunks = self._recursive_chunk(text)
        else:
            chunks = self._fixed_length_chunk(text)

        # 添加元数据
        result = []
        for i, chunk_text in enumerate(chunks):
            meta = dict(metadata or {})
            meta.update({
                "chunk_index": i,
                "chunk_total": len(chunks),
            })
            result.append({
                "text": chunk_text,
                "metadata": meta,
                "chunk_index": i,
                "chunk_total": len(chunks),
            })
        return result

    def _fixed_length_chunk(self, text: str) -> List[str]:
        """固定长度分块，带重叠"""
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk = text[start:end]
            chunks.append(chunk.strip())
            start += self.chunk_size - self.chunk_overlap
            if start >= end:
                break

        return [c for c in chunks if c]

    def _paragraph_chunk(self, text: str) -> List[str]:
        """按段落分块（基于换行符）"""
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks if chunks else self._fixed_length_chunk(text)

    def _recursive_chunk(self, text: str) -> List[str]:
        """递归分块：先按段落，再按句子，最后固定长度"""
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(para) > self.chunk_size:
                # 段落太长，按句子分
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                sentence_chunks = self._split_by_sentences(para)
                chunks.extend(sentence_chunks)
            elif len(current_chunk) + len(para) + 2 <= self.chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks if chunks else self._fixed_length_chunk(text)

    def _split_by_sentences(self, text: str) -> List[str]:
        """按句子分块，保持上下文"""
        # 中文句子结束符 + 英文句子结束符
        sentences = re.split(r'(?<=[。！？.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current_chunk = ""

        for sent in sentences:
            if len(current_chunk) + len(sent) + 1 <= self.chunk_size:
                current_chunk += sent + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sent + " "

        if current_chunk:
            chunks.append(current_chunk.strip())

        # 如果句子分块后还有太长的，用固定长度
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > self.chunk_size:
                final_chunks.extend(self._fixed_length_chunk(chunk))
            else:
                final_chunks.append(chunk)

        return final_chunks

    def chunk_by_sections(
        self,
        sections: List["DocumentSection"],
        metadata: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """按 section 边界分块，不在 section 之间合并。"""
        result: List[Dict[str, Any]] = []
        running_idx = 0
        for section in sections:
            text = (section.text or "").strip()
            if not text:
                continue
            sec_meta = dict(metadata or {})
            sec_meta.update({
                "section_id": section.section_id,
                "section_title": section.title,
                "parent_section_id": section.section_id,
            })
            if section.page_or_slide is not None:
                sec_meta["page_or_slide"] = section.page_or_slide
            for piece in self.chunk(text, metadata=sec_meta):
                piece["chunk_index"] = running_idx
                piece["metadata"]["chunk_index"] = running_idx
                result.append(piece)
                running_idx += 1
        total = len(result)
        for piece in result:
            piece["chunk_total"] = total
            piece["metadata"]["chunk_total"] = total
        return result
