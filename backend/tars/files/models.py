"""TARS Files - 数据模型"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class FileRecord:
    file_id: str
    name: str
    type: str           # "image" | "document"
    mime_type: str
    size: int
    path: str
    created_at: datetime
    user_id: str = "default"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_id": self.file_id,
            "name": self.name,
            "type": self.type,
            "mime_type": self.mime_type,
            "size": self.size,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ParsedContent:
    type: str                           # "image" | "text"
    text: Optional[str] = None
    image_base64: Optional[str] = None
    mime_type: Optional[str] = None
    truncated: bool = False
    ocr_text: Optional[str] = None
