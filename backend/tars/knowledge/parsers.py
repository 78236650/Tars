"""知识库文档解析器。"""
from __future__ import annotations

import csv
import os
import re


def _read_text_file(file_path: str) -> str:
    """Try UTF-8 first, then common Chinese legacy encodings."""
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


class TextParser:
    def parse(self, file_path: str) -> str:
        return _read_text_file(file_path)


class MarkdownParser:
    def parse(self, file_path: str) -> str:
        text = _read_text_file(file_path)
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


class CSVParser:
    def parse(self, file_path: str) -> str:
        text = _read_text_file(file_path)
        try:
            from io import StringIO

            reader = csv.reader(StringIO(text))
            rows = [", ".join(cell.strip() for cell in row if cell is not None) for row in reader]
            return "\n".join(r for r in rows if r).strip()
        except Exception:
            return text.strip()


class XLSXParser:
    def parse(self, file_path: str) -> str:
        try:
            from openpyxl import load_workbook
        except ImportError as e:
            raise ValueError("解析 .xlsx 需要安装 openpyxl") from e

        wb = load_workbook(file_path, read_only=True, data_only=True)
        lines: list[str] = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                if cells:
                    lines.append(", ".join(cells))
        wb.close()
        return "\n".join(lines).strip()


class DocumentParser:
    """按文件扩展名选择解析器。"""

    def __init__(self):
        self._parsers = {
            ".txt": TextParser(),
            ".md": MarkdownParser(),
            ".pdf": PDFParser(),
            ".docx": DOCXParser(),
            ".csv": CSVParser(),
            ".xlsx": XLSXParser(),
        }

    def parse(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        parser = self._parsers.get(ext)
        if not parser:
            raise ValueError(f"暂不支持的文档类型: {ext or 'unknown'}")
        return parser.parse(file_path)
