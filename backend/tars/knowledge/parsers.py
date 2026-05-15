"""知识库文档解析器。"""
from __future__ import annotations

import os
import re


class TextParser:
    def parse(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()


class MarkdownParser:
    def parse(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        # 保留结构信息，去掉大部分 markdown 标记。
        text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"`{1,3}", "", text)
        text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
        return text.strip()


class PDFParser:
    def parse(self, file_path: str) -> str:
        import fitz

        texts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                texts.append(page.get_text("text"))
        return "\n".join(t for t in texts if t).strip()


class DOCXParser:
    def parse(self, file_path: str) -> str:
        from docx import Document

        document = Document(file_path)
        return "\n".join(p.text for p in document.paragraphs if p.text).strip()


class DocumentParser:
    """按文件扩展名选择解析器。"""

    def __init__(self):
        self._parsers = {
            ".txt": TextParser(),
            ".md": MarkdownParser(),
            ".pdf": PDFParser(),
            ".docx": DOCXParser(),
        }

    def parse(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        parser = self._parsers.get(ext)
        if not parser:
            raise ValueError(f"暂不支持的文档类型: {ext or 'unknown'}")
        return parser.parse(file_path)
