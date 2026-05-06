"""SkillHub 数据模型"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SkillHubPackage:
    id: str
    name: str
    description: str
    author: str
    version: str
    type: str = "plugin"  # "plugin" | "prompt"
    tags: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    github_url: str = ""
    download_url: str = ""
    checksum: Optional[str] = None
    downloads: int = 0
    stars: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "type": self.type,
            "tags": self.tags,
            "permissions": self.permissions,
            "github_url": self.github_url,
            "download_url": self.download_url,
            "downloads": self.downloads,
            "stars": self.stars,
        }
