"""TARS Files - 存储管理"""
import base64
import io
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from .models import FileRecord


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
TEXT_EXTENSIONS = {".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
                   ".html", ".css", ".xml", ".csv", ".log", ".sh", ".toml", ".ini"}
DOC_EXTENSIONS = {".pdf", ".docx", ".xlsx"}

FILE_RETENTION_SECONDS = 24 * 3600  # 24 hours


class FileStorage:
    """文件存储管理器"""

    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._records: Dict[str, FileRecord] = {}

    def _detect_type(self, filename: str) -> tuple[str, str]:
        """返回 (type, mime_type)"""
        ext = Path(filename).suffix.lower()

        if ext in IMAGE_EXTENSIONS:
            mime = {
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".gif": "image/gif",
                ".webp": "image/webp", ".bmp": "image/bmp",
            }.get(ext, "image/png")
            return "image", mime
        if ext == ".pdf":
            return "document", "application/pdf"
        if ext == ".docx":
            return "document", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if ext == ".xlsx":
            return "document", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if ext == ".csv":
            return "document", "text/csv"
        if ext in TEXT_EXTENSIONS:
            return "document", "text/plain"

        return "document", "application/octet-stream"

    async def save(self, filename: str, content: bytes) -> FileRecord:
        """保存文件，返回 FileRecord"""
        file_id = f"f_{uuid.uuid4().hex[:12]}"
        file_type, mime_type = self._detect_type(filename)

        file_dir = self.upload_dir / file_id
        file_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name
        file_path = file_dir / safe_name

        with open(file_path, "wb") as f:
            f.write(content)

        record = FileRecord(
            file_id=file_id,
            name=safe_name,
            type=file_type,
            mime_type=mime_type,
            size=len(content),
            path=str(file_path),
            created_at=datetime.now(),
        )
        self._records[file_id] = record
        return record

    def get(self, file_id: str) -> Optional[FileRecord]:
        return self._records.get(file_id)

    def delete(self, file_id: str) -> bool:
        record = self._records.get(file_id)
        if not record:
            return False
        try:
            file_dir = Path(record.path).parent
            if file_dir.exists():
                shutil.rmtree(file_dir)
            del self._records[file_id]
            return True
        except Exception:
            return False

    def generate_preview(self, record: FileRecord) -> str:
        """生成预览。图片返回缩略图 base64 data URL，文档返回前 200 字符"""
        if record.type == "image":
            return self._image_thumbnail(record)
        return self._doc_text_preview(record)

    def _image_thumbnail(self, record: FileRecord) -> str:
        try:
            from PIL import Image
            img = Image.open(record.path)
            img.thumbnail((200, 200))
            buf = io.BytesIO()
            fmt = "PNG" if record.mime_type == "image/png" else "JPEG"
            if fmt == "JPEG" and img.mode != "RGB":
                img = img.convert("RGB")
            img.save(buf, format=fmt)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            return f"data:image/{fmt.lower()};base64,{b64}"
        except Exception:
            return ""

    def _doc_text_preview(self, record: FileRecord) -> str:
        """文档预览：前 200 字符文本"""
        try:
            ext = Path(record.name).suffix.lower()
            if ext in TEXT_EXTENSIONS:
                with open(record.path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read(200)
        except Exception:
            pass
        return ""

    def cleanup_expired(self) -> int:
        """清理过期文件，返回清理数量"""
        now = time.time()
        expired = []
        for file_id, rec in self._records.items():
            age = now - rec.created_at.timestamp()
            if age > FILE_RETENTION_SECONDS:
                expired.append(file_id)
        for fid in expired:
            self.delete(fid)
        return len(expired)
